"""Phase 3 networks (MASTER_PROMPT §8). Common contract:

    forward(x, s_in, s_out) -> (B, D, C, 3, h, w)
    x      (B, T_in, C_in, h, w)  normalised values, validity masks and static layers, stacked on C_in
    s_in   (B, T_in)  calendar quarter (0-3) of each input step
    s_out  (B, D)     calendar quarter of each output step (distance 1..D after the last input)
    output: q10 / q50 / q90 for the C predicted channels, direct multi-horizon (no rollout).

The input channel layout is fixed by `Layout` so models can tell optical, SAR, masks and static apart.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass(frozen=True)
class Layout:
    optical: tuple[int, ...]      # value channel positions in x (e.g. NDVI NDMI NDWI)
    sar: tuple[int, ...]          # VV VH
    opt_mask: tuple[int, ...]
    sar_mask: tuple[int, ...]
    static: tuple[int, ...]
    n_out: int                    # predicted channels C

    @property
    def n_in(self) -> int:
        return len(self.optical) + len(self.sar) + len(self.opt_mask) + len(self.sar_mask) + len(self.static)


def season_planes(s: torch.Tensor, h: int, w: int) -> torch.Tensor:
    """(B, T) quarter ids -> (B, T, 4, h, w) one-hot planes."""
    return F.one_hot(s.long(), 4).float()[..., None, None].expand(*s.shape, 4, h, w)


# ----------------------------------------------------------------------------- ConvLSTM (v1 continuity, small)
class ConvLSTMCell(nn.Module):
    def __init__(self, cin, hid, k=3):
        super().__init__()
        self.hid = hid
        self.conv = nn.Conv2d(cin + hid, 4 * hid, k, padding=k // 2)

    def forward(self, x, state):
        h, c = state
        i, f, o, g = self.conv(torch.cat([x, h], 1)).chunk(4, 1)
        c = torch.sigmoid(f) * c + torch.sigmoid(i) * torch.tanh(g)
        h = torch.sigmoid(o) * torch.tanh(c)
        return h, c


class ConvLSTM(nn.Module):
    def __init__(self, layout: Layout, D: int, hid: int = 32, layers: int = 2):
        super().__init__()
        self.D, self.C = D, layout.n_out
        cin = layout.n_in + 4
        self.cells = nn.ModuleList([ConvLSTMCell(cin if i == 0 else hid, hid) for i in range(layers)])
        self.head = nn.Sequential(nn.Conv2d(hid, hid, 3, padding=1), nn.GELU(), nn.Conv2d(hid, D * self.C * 3, 1))

    def forward(self, x, s_in, s_out):
        B, T, _, h, w = x.shape
        x = torch.cat([x, season_planes(s_in, h, w)], 2)
        states = [(x.new_zeros(B, c.hid, h, w), x.new_zeros(B, c.hid, h, w)) for c in self.cells]
        for t in range(T):
            inp = x[:, t]
            for i, cell in enumerate(self.cells):
                states[i] = cell(inp, states[i])
                inp = states[i][0]
        return self.head(inp).view(B, self.D, self.C, 3, h, w)


# ----------------------------------------------------------------------------- SimVP (Gao et al. 2022), own implementation
class GSTA(nn.Module):
    """Gated spatiotemporal attention block (SimVP v2 translator): large-kernel depthwise conv with gating."""

    def __init__(self, dim):
        super().__init__()
        self.norm = nn.BatchNorm2d(dim)
        self.dw = nn.Conv2d(dim, dim, 5, padding=2, groups=dim)
        self.dwd = nn.Conv2d(dim, dim, 7, padding=9, dilation=3, groups=dim)
        self.pw = nn.Conv2d(dim, 2 * dim, 1)
        self.mlp = nn.Sequential(nn.BatchNorm2d(dim), nn.Conv2d(dim, 4 * dim, 1), nn.GELU(), nn.Conv2d(4 * dim, dim, 1))

    def forward(self, x):
        a, g = self.pw(self.dwd(self.dw(self.norm(x)))).chunk(2, 1)
        x = x + torch.sigmoid(g) * a
        return x + self.mlp(x)


class SimVP(nn.Module):
    def __init__(self, layout: Layout, D: int, T_in: int, hid_s: int = 32, hid_t: int = 128, n_t: int = 4):
        super().__init__()
        self.D, self.C = D, layout.n_out
        cin = layout.n_in + 4

        def down(a, b):
            return nn.Sequential(nn.Conv2d(a, b, 3, 2, 1), nn.GroupNorm(4, b), nn.SiLU())

        self.enc = nn.Sequential(nn.Conv2d(cin, hid_s, 3, 1, 1), nn.GroupNorm(4, hid_s), nn.SiLU(),
                                 down(hid_s, hid_s), down(hid_s, hid_s))
        self.mix_in = nn.Conv2d(T_in * hid_s, hid_t, 1)
        self.trans = nn.Sequential(*[GSTA(hid_t) for _ in range(n_t)])
        self.mix_out = nn.Conv2d(hid_t, D * hid_s, 1)
        self.out_season = nn.Embedding(4, hid_s)

        def up(a, b):
            return nn.Sequential(nn.Conv2d(a, 4 * b, 3, 1, 1), nn.PixelShuffle(2), nn.GroupNorm(4, b), nn.SiLU())

        self.dec = nn.Sequential(up(hid_s, hid_s), up(hid_s, hid_s))
        self.head = nn.Conv2d(2 * hid_s, self.C * 3, 1)
        self.hid_s = hid_s

    def forward(self, x, s_in, s_out):
        B, T, _, h, w = x.shape
        x = torch.cat([x, season_planes(s_in, h, w)], 2).flatten(0, 1)
        e = self.enc[:3](x)                                           # full-res skip (B*T, hid_s, h, w)
        z = self.enc[3:](e)
        hz, wz = z.shape[-2:]
        z = self.trans(self.mix_in(z.view(B, T * self.hid_s, hz, wz)))
        z = self.mix_out(z).view(B, self.D, self.hid_s, hz, wz)
        z = z + self.out_season(s_out.long())[..., None, None]
        z = self.dec(z.flatten(0, 1))                                 # (B*D, hid_s, h, w)
        skip = e.view(B, T, self.hid_s, h, w)[:, -1:].expand(B, self.D, self.hid_s, h, w).flatten(0, 1)
        return self.head(torch.cat([z, skip], 1)).view(B, self.D, self.C, 3, h, w)


# ----------------------------------------------------------------------------- EcoTransformer v2
class Block(nn.Module):
    def __init__(self, dim, heads, mlp=4, drop=0.0):
        super().__init__()
        self.n1, self.n2 = nn.LayerNorm(dim), nn.LayerNorm(dim)
        self.att = nn.MultiheadAttention(dim, heads, dropout=drop, batch_first=True)
        self.mlp = nn.Sequential(nn.Linear(dim, mlp * dim), nn.GELU(), nn.Dropout(drop), nn.Linear(mlp * dim, dim))

    def forward(self, x, kv=None):
        q = self.n1(x)
        k = q if kv is None else kv
        x = x + self.att(q, k, k, need_weights=False)[0]
        return x + self.mlp(self.n2(x))


class EcoTransformerV2(nn.Module):
    """(1) direct multi-horizon queries; (2) masks + static as inputs; (3) T_in-quarter input; (4) quantile heads;
    (5) SAR fusion: 'gate' (SAR-conditioned gate over optical features), 'concat' (plain), or 'off';
    (7) learned quarter-of-year embedding on inputs and on output queries. Factorised time / space attention
    over p x p pixel tokens."""

    def __init__(self, layout: Layout, D: int, T_in: int, dim: int = 128, depth: int = 4, heads: int = 4,
                 patch: int = 8, sar: str = "gate", drop: float = 0.1):
        super().__init__()
        self.L, self.D, self.C, self.p, self.sar = layout, D, layout.n_out, patch, sar
        n_opt = len(layout.optical) + len(layout.opt_mask)
        n_sar = len(layout.sar) + len(layout.sar_mask)
        pe = lambda c: nn.Conv2d(c, dim, patch, patch)                          # noqa: E731
        if sar == "concat":
            self.embed = pe(n_opt + n_sar)
        else:
            self.embed = pe(n_opt)
            if sar == "gate":
                self.embed_sar = pe(n_sar)
                self.gate = nn.Linear(2 * dim, dim)
        self.embed_static = pe(len(layout.static))
        self.season = nn.Embedding(4, dim)
        self.time = nn.Parameter(torch.zeros(T_in, dim))
        self.horizon = nn.Parameter(torch.randn(D, dim) * 0.02)
        self.t_blocks = nn.ModuleList([Block(dim, heads, drop=drop) for _ in range(depth)])
        self.s_blocks = nn.ModuleList([Block(dim, heads, drop=drop) for _ in range(depth)])
        self.dec_cross = Block(dim, heads, drop=drop)
        self.dec_space = Block(dim, heads, drop=drop)
        self.out = nn.Sequential(nn.LayerNorm(dim), nn.Linear(dim, self.C * 3 * patch * patch))

    def _space_pos(self, n, dim, device):
        # fixed 2D sin-cos position code (works for any patch grid)
        n = int(n)                                   # a plain int in training; a traced constant for ONNX export
        g = int(round(n ** 0.5))
        y, x = torch.meshgrid(torch.arange(g, device=device), torch.arange(n // g, device=device), indexing="ij")
        f = torch.exp(torch.arange(0, dim // 4, device=device) * (-4.0 / (dim // 4)))
        enc = [torch.sin(y.flatten()[:, None] * f), torch.cos(y.flatten()[:, None] * f),
               torch.sin(x.flatten()[:, None] * f), torch.cos(x.flatten()[:, None] * f)]
        return torch.cat(enc, 1)

    def forward(self, x, s_in, s_out):
        B, T, _, h, w = x.shape
        L = self.L
        sel = lambda idx: x[:, :, list(idx)].flatten(0, 1)                     # noqa: E731
        opt = sel(L.optical + L.opt_mask)
        sar = sel(L.sar + L.sar_mask)
        if self.sar == "concat":
            f = self.embed(torch.cat([opt, sar], 1))
        else:
            f = self.embed(opt)
            if self.sar == "gate":
                fs = self.embed_sar(sar)
                g = torch.sigmoid(self.gate(torch.cat([f, fs], 1).permute(0, 2, 3, 1))).permute(0, 3, 1, 2)
                f = g * f + (1 - g) * fs
        hp, wp = f.shape[-2:]
        N, dim = hp * wp, f.shape[1]
        f = f.flatten(2).transpose(1, 2).view(B, T, N, dim)
        st = self.embed_static(x[:, -1, list(L.static)]).flatten(2).transpose(1, 2)        # (B, N, dim)
        f = f + st[:, None] + self.season(s_in.long())[:, :, None] + self.time[None, :, None]
        f = f + self._space_pos(N, dim, x.device)[None, None]
        for tb, sb in zip(self.t_blocks, self.s_blocks):
            f = tb(f.transpose(1, 2).reshape(B * N, T, dim)).view(B, N, T, dim).transpose(1, 2)
            f = sb(f.reshape(B * T, N, dim)).view(B, T, N, dim)
        q = (self.horizon[None] + self.season(s_out.long()))[:, :, None] + st[:, None]       # (B, D, N, dim)
        q = q.transpose(1, 2).reshape(B * N, self.D, dim)
        q = self.dec_cross(q, kv=f.transpose(1, 2).reshape(B * N, T, dim))
        q = q.view(B, N, self.D, dim).transpose(1, 2).reshape(B * self.D, N, dim)
        q = self.dec_space(q)
        o = self.out(q).view(B, self.D, hp, wp, self.C, 3, self.p, self.p)
        return o.permute(0, 1, 4, 5, 2, 6, 3, 7).reshape(B, self.D, self.C, 3, hp * self.p, wp * self.p)


def build(name: str, layout: Layout, D: int, T_in: int, **kw) -> nn.Module:
    if name == "convlstm":
        return ConvLSTM(layout, D, **kw)
    if name == "simvp":
        return SimVP(layout, D, T_in, **kw)
    if name == "ecotransformer":
        return EcoTransformerV2(layout, D, T_in, **kw)
    raise ValueError(name)
