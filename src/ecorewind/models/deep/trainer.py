"""Deep models behind the Phase 2 harness interface (fit(split) / predict(split, idx)), MASTER_PROMPT §8.

One network is trained per (site, track, cutoff, test fold, seed), on the cutoff's pre-cutoff history only:
  - samples: random patch x random anchor quarter p inside the history; input = quarters p-T_in+1..p,
    targets = quarters p+1..p+D that are still pre-cutoff (later distances are masked out of the loss);
  - loss pixels: training folds, outside the split buffers of the test and calibration folds, inside the AOI;
  - validation (early stopping, checkpoint selection, kill criterion): NDVI R² on calibration-fold eval pixels,
    on pairs that also lie entirely inside the pre-cutoff history (the calibration fold's post-cutoff targets are
    never seen in training);
  - prediction: anchor = last pre-cutoff quarter, whole grid tiled with overlapping patches (centre-weighted),
    read off at the pixel table's pixels for the split's target distances (lead 0 = distance 1).
Inputs: 5 predicted channels (median / IQR from training pixels' history), their validity masks, static layers.
Invalid inputs are filled with the pixel's pre-cutoff seasonal climatology, else 0 (the median).
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ...data.blocks import block_ids, split_buffer
from ..baselines.simple import Baseline, season

QUANTILES = (0.1, 0.5, 0.9)
STATIC = ("elevation_m", "coast_dist_m", "lc_tree", "lc_grass", "lc_water", "lc_herb_wetland", "lc_mangrove", "lc_other")
OPTICAL, SAR = ("NDVI", "NDMI", "NDWI"), ("VV", "VH")

_HIST_CACHE: dict = {}


def _robust(v: np.ndarray) -> tuple[float, float]:
    v = v[np.isfinite(v)]
    if not len(v):
        return 0.0, 1.0
    q25, q50, q75 = np.percentile(v, [25, 50, 75])
    return float(q50), float(max(q75 - q25, 1e-6))


class History:
    """Normalised, gap-filled pre-cutoff stack for one (cube, cutoff), shared by all folds and models."""

    def __init__(self, ctx: dict, split, train_mask: np.ndarray):
        from ...data.cube import Cube
        tab = split.table
        cube = Cube(ctx["cube"])
        self.channels = list(tab.channels)
        self.hist_idx_table = list(split.hist_idx)
        keys = [tab.keys[i] for i in split.hist_idx]
        cube_t = [cube.keys.index(k) for k in keys]
        self.seasons = np.array([season(k) for k in keys])
        T, C, (H, W) = len(keys), len(self.channels), cube.shape
        raw = np.full((T, C, H, W), np.nan, dtype="float32")
        for j, t in enumerate(cube_t):
            for ci, ch in enumerate(self.channels):
                k = cube.channel(ch)
                raw[j, ci] = np.where(np.asarray(cube.valid[t, k]), np.asarray(cube.data[t, k]), np.nan)
        rng = np.random.default_rng(0)
        rr, cc = np.nonzero(train_mask)
        pick = rng.choice(len(rr), min(200_000, len(rr)), replace=False)
        self.stats = [_robust(raw[:, ci, rr[pick], cc[pick]].ravel()) for ci in range(C)]
        for ci, (m, s) in enumerate(self.stats):
            raw[:, ci] = (raw[:, ci] - m) / s
        self.valid = np.isfinite(raw)
        with np.errstate(invalid="ignore"), __import__("warnings").catch_warnings():
            __import__("warnings").simplefilter("ignore", RuntimeWarning)
            seas = np.stack([np.nanmean(raw[self.seasons == q], 0) if (self.seasons == q).any()
                             else np.full(raw.shape[1:], np.nan, "float32") for q in range(4)])
        filled = raw.copy()
        for j in range(T):
            f = np.nan_to_num(seas[self.seasons[j]], nan=0.0)
            filled[j] = np.where(self.valid[j], raw[j], f)
        self.x = filled.astype("float16")                         # (T, C, H, W) inputs
        self.target = np.where(self.valid, raw, np.nan).astype("float16")   # never filled
        st = np.load(ctx["static"])
        layers = []
        for k in STATIC:
            a = st[k].astype("float32") if k in st.files else np.zeros((H, W), "float32")
            if not k.startswith("lc_"):
                m, s = _robust(a[train_mask])
                a = np.nan_to_num((a - m) / s, nan=0.0)
            layers.append(np.clip(a, -10, 10))
        self.static = np.stack(layers).astype("float16")
        self.shape = (H, W)


class DeepModel(Baseline):
    quantile = True

    def __init__(self, arch: str, cfg: dict, ctx: dict, seed: int = 0, sar: str = "gate", fast: bool = False,
                 variant: str = ""):
        """variant (Phase 5, '-'-joined flags, e.g. 'smooth', 'nostatic', 'tin4', 'nbr', 'xfer'):
        smooth   + temporal-smoothness penalty on consecutive median leads (weight cfg smooth_weight)
        nostatic   static layers zeroed;  nomask  validity-mask channels zeroed
        tin<N>   input length N quarters
        nbr      neighbour-informed (amendment A5): inputs and targets are anomalies from the same-quarter mean of
                 inland training-fold donor pixels of the same land-cover class; the forecast adds back the donors'
                 observed post-cutoff mean (uses post-cutoff information, like synth_control)
        xfer     cross-site transfer: trained on the other site's Track B event history, applied here"""
        self.arch, self.cfg, self.ctx, self.seed, self.sar, self.fast = arch, cfg, ctx, seed, sar, fast
        self.variant = variant
        self.v = {f: True for f in variant.split("-") if f and not f.startswith("tin")}
        tin = [f for f in variant.split("-") if f.startswith("tin")]
        self.v_tin = int(tin[0][3:]) if tin else None
        base = f"{arch}{'' if sar == 'gate' or arch != 'ecotransformer' else '_' + sar}"
        self.name = f"{base}__{variant}_s{seed}" if variant else f"{base}_s{seed}"
        self._out = None
        self._nbr = None

    # ------------------------------------------------------------------ data
    def _masks(self, split, ctx=None):
        ctx = ctx or self.ctx
        f = np.load(ctx["folds"])
        fold, aoi, fob = f["fold"], f["aoi"], f["fold_of_block"]
        res, bm, buf = ctx["res"], ctx["block_m"], ctx["buffer_m"]
        sb = f["split_buffer"] if "split_buffer" in f.files else None
        def buffer(k):
            return sb[k] if sb is not None else split_buffer(fob, k, fold.shape, res, bm, buf)
        cal = split.cal_fold
        train = aoi & (fold != split.k) & (fold != cal) & ~buffer(split.k) & ~buffer(cal)
        val = np.zeros(fold.shape, bool)
        tab = split.table
        sel = tab.fold == cal
        val[tab.r[sel], tab.c[sel]] = True
        return train, val

    def _history(self, split, train, ctx=None):
        ctx = ctx or self.ctx
        key = (str(ctx["cube"]), split.cutoff.name, split.k)
        if key not in _HIST_CACHE:
            _HIST_CACHE.clear()                                    # one (cutoff, fold) in memory at a time
            _HIST_CACHE[key] = History(ctx, split, train)
        return _HIST_CACHE[key]

    def _sample(self, h: History, mask: np.ndarray, origins, anchors, n, rng, T_in, D, size):
        X, S_in, S_out, Y, M = [], [], [], [], []
        for _ in range(n):
            r, c = origins[rng.integers(len(origins))]
            p = anchors[rng.integers(len(anchors))]
            X.append(self._input(h, p, r, c, size, T_in))
            S_in.append(self._seasons_in(h, p, T_in))
            S_out.append([(h.seasons[p] + d) % 4 for d in range(1, D + 1)])
            y = np.full((D, len(h.channels), size, size), np.nan, "float32")
            for d in range(1, D + 1):
                if p + d < len(h.seasons):
                    y[d - 1] = h.target[p + d, :, r:r + size, c:c + size]
                    if self._nbr is not None:
                        y[d - 1] -= self._nbr["hist"][p + d][:, self._nbr["cls"][r:r + size, c:c + size]]
            m = np.isfinite(y) & mask[None, None, r:r + size, c:c + size]
            Y.append(np.nan_to_num(y))
            M.append(m)
        return [np.stack(a) for a in (X, S_in, S_out, Y, M)]

    @staticmethod
    def _seasons_in(h: History, p, T_in):
        """Calendar quarters of the T_in input steps ending at p (steps before the series are extrapolated)."""
        return np.array([(h.seasons[p] - (T_in - 1 - j)) % 4 for j in range(T_in)])

    def _input(self, h: History, p, r, c, size, T_in):
        """Inputs for the T_in quarters ending at p. Early anchors (p < T_in - 1) are left-padded with zeros and
        validity 0, so short placebo histories still give training pairs at every target distance."""
        lo = max(0, p - T_in + 1)
        x = h.x[lo:p + 1, :, r:r + size, c:c + size].astype("float32")
        m = h.valid[lo:p + 1, :, r:r + size, c:c + size].astype("float32")
        pad = T_in - x.shape[0]
        if pad:
            z = np.zeros((pad, *x.shape[1:]), "float32")
            x, m = np.concatenate([z, x]), np.concatenate([z, m])
        if self._nbr is not None:
            M = self._nbr["hist"][lo:p + 1][:, :, self._nbr["cls"][r:r + size, c:c + size]]   # (t, C, h, w)
            x[pad:] -= M
        if self.v.get("nomask"):
            m = np.zeros_like(m)
        st = np.broadcast_to(h.static[:, r:r + size, c:c + size], (T_in, len(STATIC), size, size)).astype("float32")
        if self.v.get("nostatic"):
            st = np.zeros_like(st)
        return np.concatenate([x, m, st], 1)

    def _layout(self, channels):
        from .nets import Layout
        C = len(channels)
        opt = tuple(channels.index(c) for c in OPTICAL)
        sar = tuple(channels.index(c) for c in SAR)
        return Layout(opt, sar, tuple(C + i for i in opt), tuple(C + i for i in sar),
                      tuple(range(2 * C, 2 * C + len(STATIC))), C)

    # ------------------------------------------------------------------ fit / predict
    def _cache_file(self, split) -> Path:
        tab = split.table
        key = [tab.data_hash, self.cfg] + ([self.variant] if self.variant else [])
        tag = hashlib.sha1(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:8]
        return Path(self.ctx["cache"]) / f"{tab.site}_{tab.track}_{self.name}_{split.cutoff.name}_k{split.k}_{tag}.npz"

    def fit(self, split):
        self._split = split
        self._out = None
        return self

    def _train_and_predict(self, split):
        cf = self._cache_file(split)
        if cf.exists():
            z = np.load(cf)
            self.info = json.loads(str(z["info"]))
            return z["out"].astype("float32"), [int(d) for d in z["dists"]]
        import torch
        from .nets import build
        cfg, log = self.cfg, self.ctx.get("log", print)
        tab = split.table
        size = cfg["patch"][tab.track]
        T_in = self.v_tin or cfg["T_in"][tab.track]
        dists = sorted(set(split.distance()))
        D = max(dists)
        t_load = time.time()
        if self.v.get("xfer"):                                      # train on the other site's Track B event history
            fit_split, fit_ctx = self.ctx["make_source"](split)
            log(f"    {self.name}: training on {fit_split.table.site} {fit_split.cutoff.name} k{fit_split.k} (transfer)")
        else:
            fit_split, fit_ctx = split, self.ctx
        train, val = self._masks(fit_split, fit_ctx)
        log(f"    {self.name} {split.cutoff.name} k{split.k}: loading pre-cutoff history ...")
        h = self._history(fit_split, train, fit_ctx)
        log(f"    history ready: {len(h.seasons)} quarters, grid {h.shape[0]}x{h.shape[1]} ({time.time() - t_load:.0f}s)")
        self._nbr = self._neighbour_means(split, h, fit_ctx) if self.v.get("nbr") else None
        n_hist = len(h.seasons)
        # anchors need >= min_history observed quarters; inputs shorter than T_in are zero-padded (masked)
        anchors = list(range(min(cfg.get("min_history", T_in), T_in) - 1, n_hist - 1))
        if not anchors:
            raise ValueError(f"{split.cutoff.name}: {n_hist} history quarters is too short")
        H, W = h.shape
        stride = max(1, size // 2)
        grid = [(r, c) for r in range(0, H - size + 1, stride) for c in range(0, W - size + 1, stride)]
        tr_orig = [(r, c) for r, c in grid if train[r:r + size, c:c + size].mean() > 0.25]
        va_orig = [(r, c) for r, c in grid if val[r:r + size, c:c + size].mean() > 0.25]
        if not tr_orig or not va_orig:
            raise ValueError("no training / validation patches")
        torch.manual_seed(self.seed)
        rng = np.random.default_rng(self.seed)
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        kw = dict(cfg.get("arch", {}).get(self.arch, {}))
        if self.arch == "ecotransformer":
            kw["sar"] = self.sar
        net = build(self.arch, self._layout(h.channels), D, T_in, **kw).to(dev)
        epochs, steps, bs = cfg["epochs"], cfg["steps_per_epoch"], cfg["batch"][tab.track]
        if self.fast:
            epochs, steps, bs = 1, 2, 2
        opt = torch.optim.AdamW(net.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
        sched = torch.optim.lr_scheduler.OneCycleLR(opt, cfg["lr"], total_steps=epochs * steps, pct_start=0.1,
                                                    anneal_strategy="cos")
        amp = dev == "cuda"
        scaler = torch.amp.GradScaler("cuda", enabled=amp)
        q = torch.tensor(QUANTILES, device=dev).view(1, 1, 1, 3, 1, 1)
        val_anchors = anchors                                    # all anchors: validation covers every distance
        vrng = np.random.default_rng(1234)
        vb = self._sample(h, val, va_orig, val_anchors, 4 if self.fast else cfg["val_samples"], vrng, T_in, D, size)
        ndvi = h.channels.index("NDVI")
        n_par = sum(p.numel() for p in net.parameters())
        log(f"    {self.arch} on {dev}: {n_par / 1e6:.2f} M params, {len(tr_orig)} train / {len(va_orig)} val patch origins, "
            f"{len(anchors)} anchors, D={D}, {epochs} epochs x {steps} steps x batch {bs}")
        best, best_state, bad, t0, hist_r2 = -math.inf, None, 0, time.time(), []
        every = max(1, steps // 5)
        killed = False
        for ep in range(epochs):
            net.train()
            te = time.time()
            for step in range(steps):
                X, Si, So, Y, M = (torch.from_numpy(a).to(dev) for a in
                                   self._sample(h, train, tr_orig, anchors, bs, rng, T_in, D, size))
                with torch.autocast(dev, dtype=torch.float16, enabled=amp):
                    out = net(X, Si, So)
                err = Y[:, :, :, None].float() - out.float()
                loss = torch.maximum(q * err, (q - 1) * err) * M[:, :, :, None]
                loss = loss.sum() / M.sum().clamp(min=1) / 3
                if self.v.get("smooth") and out.shape[1] > 1:      # ablation: temporal smoothness of the median
                    med = out[:, :, :, 1].float()
                    loss = loss + cfg.get("smooth_weight", 0.1) * ((med[:, 1:] - med[:, :-1]) ** 2).mean()
                opt.zero_grad(set_to_none=True)
                scaler.scale(loss).backward()
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
                scaler.step(opt)
                scaler.update()
                sched.step()
                if (step + 1) % every == 0:
                    sps = (step + 1) / (time.time() - te)
                    log(f"      ep{ep + 1} step {step + 1}/{steps}  loss {loss.item():.4f}  {sps:.1f} it/s"
                        f"  epoch ETA {(steps - step - 1) / sps:.0f}s")
            r2 = self._val_r2(net, vb, ndvi, dev, amp)
            hist_r2.append(r2)
            ep_s = (time.time() - t0) / (ep + 1)
            log(f"    {self.name} {split.cutoff.name} k{split.k} ep{ep + 1}/{epochs}: loss {loss.item():.4f}  "
                f"val NDVI R² {r2:.3f} (best {max(best, r2):.3f})  {time.time() - t0:.0f}s elapsed, "
                f"<= {ep_s * (epochs - ep - 1) / 60:.1f} min left" + (f"  [GPU mem {torch.cuda.max_memory_allocated() / 1e9:.1f} GB]" if amp else ""))
            if r2 > best:
                best, bad = r2, 0
                best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
            else:
                bad += 1
            if ep + 1 >= cfg["kill_after"] and best < 0 and not self.fast:
                killed = True                                      # pre-registered kill criterion
                break
            if bad >= cfg["patience"]:
                break
        self.info = {"best_val_ndvi_r2": best, "epochs": len(hist_r2), "killed": killed, "seconds": time.time() - t0,
                     "val_r2": hist_r2}
        out = np.full((D, len(h.channels), 3, tab.n), np.nan, "float32")
        if not killed and best_state is not None:
            net.load_state_dict(best_state)
            if self.ctx.get("keep_net"):                            # scripts/export_lab_model.py
                self.net = net
            if self.v.get("xfer"):                                  # predict on this site's own pre-cutoff history
                del h
                h = self._history(split, self._masks(split)[0])
            tp = time.time()
            out = self._predict_grid(net, h, T_in, D, size, dev, amp, split)[:, :, :, tab.r, tab.c]
            log(f"    predicted full grid ({time.time() - tp:.0f}s)")   # (D, C, 3, n)
        out = out.astype("float16").astype("float32")             # identical whether fresh or from the cache
        cf.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cf, out=out.astype("float16"), dists=np.arange(1, D + 1), info=json.dumps(self.info))
        log(f"    {self.name} {split.cutoff.name} k{split.k}: best val NDVI R² {best:.3f}"
            f"{' KILLED' if killed else ''} ({self.info['seconds']:.0f}s)")
        return out, list(range(1, D + 1))

    def _val_r2(self, net, vb, ci, dev, amp):
        import torch
        net.eval()
        X, Si, So, Y, M = vb
        preds = []
        with torch.no_grad():
            for i in range(0, len(X), 8):
                with torch.autocast(dev, dtype=torch.float16, enabled=amp):
                    preds.append(net(*(torch.from_numpy(a[i:i + 8]).to(dev) for a in (X, Si, So)))[:, :, ci, 1].float().cpu().numpy())
        p = np.concatenate(preds)
        y, m = Y[:, :, ci], M[:, :, ci]
        if m.sum() < 10:
            return float("nan")
        yt, pt = y[m], p[m]
        return float(1 - np.sum((yt - pt) ** 2) / max(np.sum((yt - yt.mean()) ** 2), 1e-12))

    def _neighbour_means(self, split, h: History, ctx):
        """Same-quarter mean (normalised units) of donor pixels per channel x land-cover class.
        Donors: training-fold evaluable pixels in the most inland 40 % of blocks (coast distance)."""
        tab = split.table
        lc = [i for i, k in enumerate(STATIC) if k.startswith("lc_")]
        cls = np.argmax(h.static[lc].astype("float32"), axis=0).astype("int16")          # (H, W)
        coast = h.static[STATIC.index("coast_dist_m")].astype("float32")
        bid = block_ids(h.shape, ctx["res"], ctx["block_m"])
        trainf = (tab.fold != split.k) & (tab.fold != split.cal_fold)
        tb = bid[tab.r, tab.c]
        bc = pd.Series(coast[tab.r, tab.c]).groupby(tb).median()
        inland = set(bc[bc >= bc.quantile(0.6)].index)
        don = np.nonzero(trainf & np.isin(tb, list(inland)))[0]
        dcls = cls[tab.r[don], tab.c[don]]
        K, C = len(lc), len(h.channels)

        def means(t):
            v = np.stack([(tab.Y[t, ci, don] - m) / s for ci, (m, s) in enumerate(h.stats)])   # (C, n_don)
            out = np.zeros((C, K), "float32")
            with np.errstate(invalid="ignore"), __import__("warnings").catch_warnings():
                __import__("warnings").simplefilter("ignore", RuntimeWarning)
                allm = np.nanmean(v, axis=1)
                for k in range(K):
                    mk = np.nanmean(v[:, dcls == k], axis=1) if (dcls == k).sum() >= 20 else allm
                    out[:, k] = np.where(np.isfinite(mk), mk, np.nan_to_num(allm))
            return np.nan_to_num(out)

        hist = np.stack([means(t) for t in split.hist_idx]) if len(split.hist_idx) == len(h.seasons) else None
        if hist is None:                                           # transfer + nbr is not supported
            raise ValueError("neighbour-informed variant needs the target site's own history")
        tgt = {d: means(t) for d, t in zip(split.distance(), split.tgt_idx)}
        return {"cls": cls, "hist": hist, "tgt": tgt}

    def _predict_grid(self, net, h: History, T_in, D, size, dev, amp, split=None):
        import torch
        net.eval()
        H, W = h.shape
        p = len(h.seasons) - 1
        acc = np.zeros((D, len(h.channels), 3, H, W), "float32")
        wsum = np.zeros((H, W), "float32")
        win = np.outer(np.hanning(size + 2)[1:-1], np.hanning(size + 2)[1:-1]).astype("float32") + 1e-3
        stride = size // 2
        rows = sorted(set(list(range(0, H - size + 1, stride)) + [H - size]))
        cols = sorted(set(list(range(0, W - size + 1, stride)) + [W - size]))
        si = torch.from_numpy(self._seasons_in(h, p, T_in)[None]).to(dev)
        so = torch.tensor([[(h.seasons[p] + d) % 4 for d in range(1, D + 1)]], device=dev)
        tiles = [(r, c) for r in rows for c in cols]
        B = 8
        with torch.no_grad():
            for i in range(0, len(tiles), B):
                tb = tiles[i:i + B]
                X = torch.from_numpy(np.stack([self._input(h, p, r, c, size, T_in) for r, c in tb])).to(dev)
                with torch.autocast(dev, dtype=torch.float16, enabled=amp):
                    o = net(X, si.expand(len(tb), -1), so.expand(len(tb), -1)).float().cpu().numpy()
                o = np.sort(o, axis=3)                             # no quantile crossing
                for j, (r, c) in enumerate(tb):
                    acc[..., r:r + size, c:c + size] += o[j] * win
                    wsum[r:r + size, c:c + size] += win
        acc /= np.maximum(wsum, 1e-6)
        if self._nbr is not None:                                  # add back the donors' observed same-quarter mean
            for d in range(1, D + 1):
                Mt = self._nbr["tgt"].get(d)
                for ci in range(acc.shape[1]):
                    acc[d - 1, ci] += Mt[ci][self._nbr["cls"]] if Mt is not None else np.nan
        for ci, (m, s) in enumerate(h.stats):                      # back to physical units
            acc[:, ci] = acc[:, ci] * s + m
        return acc

    def predict(self, split, idx):
        if self._out is None:
            self._out, self._dists = self._train_and_predict(split)
        pos = {d: i for i, d in enumerate(self._dists)}
        sel = [pos[d] for d in split.distance()]
        # the cache holds every table pixel; map idx -> columns
        o = self._out[sel][..., idx]                               # (L, C, 3, n)
        return o[:, :, 1], o[:, :, 0], o[:, :, 2]
