// Corvus Desktop — theme system
// Fusion of Claude's minimalism + Codex's dark professional + Reasonix's status colors

.pragma library

// ── Color palette ─────────────────────────────────────────────
// Primary:  violet-blue gradient (Claude-like warmth)
// Surface:  layered grays (Codex-like depth)
// Status:   green/amber/red (Reasonix-like clarity)

// Dark theme (default)
var bg0       = "#0d1117"   // deepest background
var bg1       = "#161b22"   // panel backgrounds
var bg2       = "#21262d"   // card backgrounds, input areas
var bg3       = "#30363d"   // borders, dividers
var fg1       = "#e6edf3"   // primary text
var fg2       = "#8b949e"   // secondary text, captions
var fg3       = "#484f58"   // muted text

var accent    = "#7c3aed"   // violet — primary accent
var accentDim = "#6d28d9"   // darker violet for hover states
var accentLit = "#a78bfa"   // lighter violet for highlights

var green     = "#3fb950"   // pass / success
var red       = "#f85149"   // fail / error
var amber     = "#d29922"   // warning / skip
var blue      = "#58a6ff"   // info / links
var cyan      = "#39d353"   // tool calls / active
var pink      = "#db61a2"   // Moss-specific highlights

// Light theme (overrides)
var light_bg0       = "#ffffff"
var light_bg1       = "#f6f8fa"
var light_bg2       = "#eaeef2"
var light_bg3       = "#d0d7de"
var light_fg1       = "#1f2328"
var light_fg2       = "#656d76"
var light_fg3       = "#8c959f"

// ── Sizing & spacing ──────────────────────────────────────────
var radius_sm  = 6
var radius_md  = 10
var radius_lg  = 16
var radius_xl  = 24

var space_xs  = 4
var space_sm  = 8
var space_md  = 12
var space_lg  = 16
var space_xl  = 24

var sidebar_w = 260   // workspace sidebar width
var detail_w  = 300   // detail panel width
var min_panel = 200   // minimum panel width before collapse

// ── Typography ────────────────────────────────────────────────
var font_mono   = "Consolas, 'Courier New', monospace"
var font_sans   = "'Segoe UI', 'SF Pro Display', system-ui, sans-serif"
var font_size_xs = 11
var font_size_sm = 12
var font_size_md = 13
var font_size_lg = 16
var font_size_xl = 20
