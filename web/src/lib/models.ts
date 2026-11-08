// Display metadata for every trained model (ids as in configs/model_registry.json and the run folders).
export type Fam = "baseline" | "deep" | "ablation" | "transfer" | "experimental";

type Meta = { name: string; short: string; color: string; fam: Fam; parent?: string; blurb: string };

export const MODEL_META: Record<string, Meta> = {
  persistence: { name: "Persistence", short: "Persistence", color: "#8a8f98", fam: "baseline", blurb: "Last value carried forward" },
  climatology: { name: "Seasonal climatology", short: "Climatology", color: "#c9a96e", fam: "baseline", blurb: "Per-pixel seasonal mean" },
  harmonic: { name: "Harmonic (trend)", short: "Harmonic", color: "#c98b5e", fam: "baseline", blurb: "Cosines + linear trend" },
  harmonic_notrend: { name: "Harmonic (no trend)", short: "Harmonic ∅t", color: "#d8bf8c", fam: "baseline", blurb: "Cosines, no trend (A1)" },
  synth_control: { name: "Synthetic control", short: "Synth. control", color: "#7fb7a8", fam: "baseline", blurb: "Matched DiD vs inland donors" },
  lgbm: { name: "LightGBM quantile", short: "LightGBM", color: "#7c9cc9", fam: "baseline", blurb: "Boosted trees on lags" },
  convlstm: { name: "ConvLSTM", short: "ConvLSTM", color: "#c47fa0", fam: "deep", blurb: "Recurrent conv network" },
  simvp: { name: "SimVP", short: "SimVP", color: "#9d8fd1", fam: "deep", blurb: "Conv encoder + gSTA translator" },
  ecotransformer: { name: "EcoTransformer v2", short: "EcoTransformer", color: "#6fb38a", fam: "deep", blurb: "SAR-gated factorised attention" },
  ecotransformer_off: { name: "EcoTransformer · SAR off", short: "EcoT · SAR off", color: "#a8bf7a", fam: "ablation", parent: "ecotransformer", blurb: "Radar input removed" },
  ecotransformer_concat: { name: "EcoTransformer · SAR concat", short: "EcoT · SAR concat", color: "#7dbf8e", fam: "ablation", parent: "ecotransformer", blurb: "Radar concatenated, no gate" },
  ecotransformer__smooth: { name: "EcoTransformer · smoothness loss", short: "EcoT · smooth", color: "#6aa9a0", fam: "ablation", parent: "ecotransformer", blurb: "Temporal smoothness penalty" },
  ecotransformer__nostatic: { name: "EcoTransformer · no static", short: "EcoT · no static", color: "#5e9e7c", fam: "ablation", parent: "ecotransformer", blurb: "DEM / land cover removed" },
  ecotransformer__nomask: { name: "EcoTransformer · no mask", short: "EcoT · no mask", color: "#95c7ad", fam: "ablation", parent: "ecotransformer", blurb: "Validity mask channel removed" },
  ecotransformer__tin4: { name: "EcoTransformer · 4-quarter input", short: "EcoT · T_in 4", color: "#b9c98a", fam: "ablation", parent: "ecotransformer", blurb: "1 year of history" },
  ecotransformer__tin12: { name: "EcoTransformer · 12-quarter input", short: "EcoT · T_in 12", color: "#4f8a6c", fam: "ablation", parent: "ecotransformer", blurb: "3 years of history" },
  simvp__xfer: { name: "SimVP · cross-site transfer", short: "SimVP · transfer", color: "#b7aedc", fam: "transfer", parent: "simvp", blurb: "Trained on the other site" },
  ecotransformer__xfer: { name: "EcoTransformer · cross-site transfer", short: "EcoT · transfer", color: "#5c9a98", fam: "transfer", parent: "ecotransformer", blurb: "Trained on the other site" },
  simvp__nbr: { name: "Neighbour-informed SimVP", short: "SimVP · neighbours", color: "#c592c9", fam: "experimental", parent: "simvp", blurb: "Sees inland donors (A5, post hoc)" },
};

export const FAM_LABEL: Record<Fam, string> = {
  baseline: "Baselines", deep: "Deep models", ablation: "Ablations", transfer: "Cross-site transfer", experimental: "Experimental",
};
export const FAM_ORDER: Fam[] = ["baseline", "deep", "ablation", "transfer", "experimental"];

const fallback = (id: string): Meta => ({ name: id.replace(/_/g, " "), short: id.replace(/_/g, " "), color: "#8fa39a", fam: "ablation", blurb: "" });
export const meta = (id: string) => MODEL_META[id] ?? fallback(id);
export const famOf = (id: string) => meta(id).fam;
export const sortModels = (ids: string[]) =>
  [...ids].sort((a, b) => FAM_ORDER.indexOf(famOf(a)) - FAM_ORDER.indexOf(famOf(b)) || Object.keys(MODEL_META).indexOf(a) - Object.keys(MODEL_META).indexOf(b));
