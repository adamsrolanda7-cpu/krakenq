#!/usr/bin/env python3
"""Génère le logo KrakenQ — un kraken à 8 tentacules — en SVG (stdlib uniquement).

    python3 build_logo.py [dossier_de_sortie]

Fichiers produits :
    logo.svg        icône complète (fond arrondi + kraken en couleur)
    logo-mark.svg   kraken seul, fond transparent (pour fonds sombres)
    logo-fullbleed.svg  icône plein cadre sans coins arrondis (apple-touch-icon, icônes « maskable »)
    logo-tight.svg  version resserrée (kraken plus grand) pour favicons et très petites tailles
    logo-mono.svg   silhouette une couleur (currentColor), fond transparent

Tout est calculé à partir de quelques paramètres (liste TENTACLES ci-dessous) :
changez un angle, une longueur ou l'enroulement d'un tentacule et relancez.
"""
import math
import os
import sys

CX = 256  # axe de symétrie
TIP = 3.5  # largeur du bout des tentacules

# Côté droit, du plus central au plus extérieur ; le côté gauche est le miroir.
#   bx/by : point d'attache (bx = décalage depuis l'axe)   th : cap initial en degrés (90 = vers le bas)
#   L : longueur   w : largeur à la base   wa/wp : amplitude/phase de l'ondulation
#   curl/cp : force et raideur de l'enroulement final (spirale)
TENTACLES = [
    dict(bx=22, by=270, th=93, L=240, w=40, wa=-0.0120, wp=0.3, curl=0.070, cp=2.4),
    dict(bx=52, by=266, th=68, L=296, w=43, wa=-0.0100, wp=0.1, curl=0.062, cp=2.4),
    dict(bx=78, by=254, th=38, L=300, w=44, wa=-0.0095, wp=0.0, curl=0.056, cp=2.4),
    dict(bx=94, by=238, th=8, L=252, w=43, wa=-0.0110, wp=0.2, curl=0.062, cp=2.4),
]

# ----------------------------------------------------------------------------
# Géométrie
# ----------------------------------------------------------------------------


def centerline(t, n=100):
    x, y, th = CX + t["bx"], t["by"], math.radians(t["th"])
    ds = t["L"] / n
    pts = []
    for i in range(n + 1):
        u = i / n
        pts.append((x, y, th, u))
        k = t["wa"] * math.sin(2 * math.pi * 1.1 * u + t["wp"]) - t["curl"] * u ** t["cp"]
        th += k * ds
        x += math.cos(th) * ds
        y += math.sin(th) * ds
    return pts


def width(t, u):
    return TIP + (t["w"] - TIP) * (1 - u) ** 1.0


def mirror(pts):
    return [(2 * CX - x, y) for x, y in pts]


def fmt(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


def smooth_closed(pts):
    """Courbe fermée lissée (quadratiques passant par les milieux)."""
    n = len(pts)
    mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    m0 = mid(pts[-1], pts[0])
    d = ["M%s,%s" % (fmt(m0[0]), fmt(m0[1]))]
    for i in range(n):
        p, q = pts[i], pts[(i + 1) % n]
        m = mid(p, q)
        d.append("Q%s,%s %s,%s" % (fmt(p[0]), fmt(p[1]), fmt(m[0]), fmt(m[1])))
    return "".join(d) + "Z"


def tapered(cl, t, off0, off1, frac_a=0.0, frac_b=1.0, side=1.0):
    """Ruban effilé le long du tentacule : décalé de off0 (par rapport à la largeur), largeur off1."""
    left, right = [], []
    for x, y, th, u in cl:
        if u < frac_a or u > frac_b:
            continue
        w = width(t, u)
        nx, ny = -math.sin(th), math.cos(th)
        c = side * off0 * w
        hw = off1 * w / 2
        left.append((x + nx * (c + hw), y + ny * (c + hw)))
        right.append((x + nx * (c - hw), y + ny * (c - hw)))
    return left + right[::-1]


def build_geometry():
    """Renvoie la liste des tentacules (côté droit puis gauche) avec contours, reflets et ventouses."""
    items = []
    for t in TENTACLES:
        cl = centerline(t)
        left, right = [], []
        for x, y, th, u in cl:
            w = width(t, u) / 2
            nx, ny = -math.sin(th), math.cos(th)
            left.append((x + nx * w, y + ny * w))
            right.append((x - nx * w, y - ny * w))
        outline = left + right[::-1]
        # reflet sur le bord extérieur (côté opposé à l'enroulement) : normale (-sinθ, cosθ) = côté extérieur
        shine = tapered(cl, t, 0.27, 0.15, 0.06, 0.82, side=1.0)
        # ventouses côté intérieur de la spirale
        suckers = []
        s_len = 0.0
        prev = None
        for x, y, th, u in cl:
            if prev is not None:
                s_len += math.hypot(x - prev[0], y - prev[1])
            prev = (x, y)
            if u < 0.20 or u > 0.975:
                continue
            w = width(t, u)
            gap = max(7.5, 1.02 * w)
            if suckers and math.hypot(x - suckers[-1][3], y - suckers[-1][4]) < gap:
                continue
            nx, ny = -math.sin(th), math.cos(th)
            ox, oy = x - nx * 0.16 * w, y - ny * 0.16 * w
            suckers.append((ox, oy, 0.27 * w, x, y))
        items.append(dict(outline=outline, shine=shine, suckers=[(a, b, r) for a, b, r, _, _ in suckers]))
    return items


def mirrored(items):
    out = []
    for it in items:
        out.append(
            dict(
                outline=mirror(it["outline"]),
                shine=mirror(it["shine"]),
                suckers=[(2 * CX - x, y, r) for x, y, r in it["suckers"]],
            )
        )
    return out


# ----------------------------------------------------------------------------
# Éléments SVG
# ----------------------------------------------------------------------------

HEAD = (
    "M256,22 C322,30 372,88 372,168 C372,226 350,262 322,282 "
    "C300,298 212,298 190,282 C162,262 140,226 140,168 C140,88 190,30 256,22Z"
)

INK = "#04111d"  # couleur des contours / de l'ombre


def tentacle_svg(items, colour=True):
    """items : liste ordonnée de l'extérieur vers l'intérieur (dessin du fond vers l'avant)."""
    out = []
    fill = "url(#kqBody)" if colour else "#fff"
    stroke = INK if colour else "#000"
    for it in items:
        out.append(
            '<path d="%s" fill="%s" stroke="%s" stroke-width="3.2" stroke-linejoin="round"/>'
            % (smooth_closed(it["outline"]), fill, stroke)
        )
        if colour:
            out.append('<path d="%s" fill="#eafffb" opacity=".20"/>' % smooth_closed(it["shine"]))
        for x, y, r in it["suckers"]:
            if colour:
                out.append(
                    '<circle cx="%s" cy="%s" r="%s" fill="#c9fff3" opacity=".92"/>'
                    '<circle cx="%s" cy="%s" r="%s" fill="#0b6a70" opacity=".55"/>'
                    % (fmt(x), fmt(y), fmt(r), fmt(x), fmt(y), fmt(r * 0.46))
                )
            else:
                out.append('<circle cx="%s" cy="%s" r="%s" fill="#000"/>' % (fmt(x), fmt(y), fmt(r * 0.82)))
    return "\n".join(out)


def head_svg(colour=True):
    out = []
    if colour:
        # ombre portée de la tête sur les tentacules
        out.append(
            '<ellipse cx="256" cy="296" rx="120" ry="24" fill="url(#kqShadow)"/>'
        )
        out.append('<path d="%s" fill="url(#kqHead)" stroke="%s" stroke-width="3.4" stroke-linejoin="round"/>' % (HEAD, INK))
        # reflet
        out.append('<ellipse cx="214" cy="96" rx="56" ry="26" transform="rotate(-32 214 96)" fill="url(#kqGloss)"/>')
        # taches
        for sx in (-1, 1):
            for dx, y, r in ((50, 84, 6), (82, 118, 4.6), (58, 126, 3.2), (96, 160, 3.6), (30, 60, 3.4)):
                out.append(
                    '<circle cx="%s" cy="%s" r="%s" fill="#0a5560" opacity=".38"/>' % (fmt(256 + sx * dx), y, r)
                )
        # trois chandeliers discrets sur le front (clin d'œil trading)
        for cx_, top, h, wick in ((238, 104, 22, 12), (256, 84, 34, 14), (274, 96, 26, 10)):
            out.append(
                '<path d="M%d,%d V%d" stroke="#0a5560" stroke-opacity=".62" stroke-width="2.4" stroke-linecap="round"/>'
                '<rect x="%d" y="%d" width="10" height="%d" rx="2.4" fill="#0a5560" fill-opacity=".62"/>'
                % (cx_, top - wick, top + h + wick, cx_ - 5, top, h)
            )
    else:
        out.append('<path d="%s" fill="#fff" stroke="#000" stroke-width="3.4" stroke-linejoin="round"/>' % HEAD)
        for sx in (-1, 1):
            for dx, y, r in ((50, 84, 5), (82, 118, 4), (96, 160, 3.4)):
                out.append('<circle cx="%s" cy="%s" r="%s" fill="#000"/>' % (fmt(256 + sx * dx), y, r))
    return "\n".join(out)


def eyes_svg(colour=True):
    out = []
    for sx in (-1, 1):
        ex, ey = 256 + sx * 52, 196
        if colour:
            out.append('<circle cx="%s" cy="%s" r="52" fill="url(#kqEyeGlow)"/>' % (ex, ey))
            out.append(
                # arcade sourcilière sombre
                '<path d="M%s,%s Q%s,%s %s,%s" fill="none" stroke="#06404b" stroke-width="11" stroke-linecap="round"/>'
                % (fmt(256 + sx * 22), 176, fmt(ex), 150, fmt(256 + sx * 84), 158)
            )
            out.append('<ellipse cx="%s" cy="%s" rx="31" ry="30" fill="%s"/>' % (ex, ey, INK))
            out.append('<circle cx="%s" cy="%s" r="25" fill="url(#kqIris)"/>' % (ex, ey))
            out.append('<circle cx="%s" cy="%s" r="25" fill="none" stroke="#7a3a05" stroke-width="2" opacity=".55"/>' % (ex, ey))
            out.append(
                '<ellipse cx="%s" cy="%s" rx="7" ry="18.5" fill="%s"/>' % (ex, ey, INK)
            )
            out.append('<circle cx="%s" cy="%s" r="5.2" fill="#fff" opacity=".95"/>' % (ex - 8, ey - 10))
            out.append('<circle cx="%s" cy="%s" r="2.4" fill="#fff" opacity=".7"/>' % (ex + 9, ey + 9))
        else:
            out.append('<ellipse cx="%s" cy="%s" rx="31" ry="30" fill="#000"/>' % (ex, ey))
            out.append('<circle cx="%s" cy="%s" r="22" fill="#fff"/>' % (ex, ey))
            out.append('<ellipse cx="%s" cy="%s" rx="7" ry="17" fill="#000"/>' % (ex, ey))
    return "\n".join(out)


def kraken_group(colour=True):
    right = build_geometry()
    left = mirrored(right)
    # ordre de dessin : extérieurs d'abord (au fond), intérieurs devant ; gauche/droite alternés
    ordered = []
    for i in range(len(right) - 1, -1, -1):
        ordered.append(right[i])
        ordered.append(left[i])
    return "\n".join([tentacle_svg(ordered, colour), head_svg(colour), eyes_svg(colour)]), right, left


def bbox(right, left):
    xs, ys = [], []
    for it in right + left:
        for x, y in it["outline"]:
            xs.append(x)
            ys.append(y)
    xs += [142, 370]
    ys += [30]
    return min(xs), min(ys), max(xs), max(ys)


def fit_transform(right, left, box_w=396, box_h=404, cy=262):
    x0, y0, x1, y1 = bbox(right, left)
    w, h = x1 - x0, y1 - y0
    s = min(box_w / w, box_h / h)
    tx = 256 - (x0 + w / 2) * s
    ty = cy - (y0 + h / 2) * s
    return "translate(%s %s) scale(%s)" % (fmt(tx), fmt(ty), "%.4f" % s)


DEFS_COLOUR = """
<linearGradient id="kqBg" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#0d2236"/><stop offset=".55" stop-color="#07131f"/><stop offset="1" stop-color="#040910"/>
</linearGradient>
<radialGradient id="kqGlow" cx="256" cy="210" r="250" gradientUnits="userSpaceOnUse">
  <stop offset="0" stop-color="#19d3bd" stop-opacity=".34"/><stop offset=".55" stop-color="#1b7fd6" stop-opacity=".10"/><stop offset="1" stop-color="#1b7fd6" stop-opacity="0"/>
</radialGradient>
<linearGradient id="kqBody" gradientUnits="userSpaceOnUse" x1="256" y1="250" x2="256" y2="500">
  <stop offset="0" stop-color="#14b8a6"/><stop offset=".45" stop-color="#1aa3c8"/><stop offset="1" stop-color="#6d5ff0"/>
</linearGradient>
<radialGradient id="kqHead" cx="226" cy="120" r="210" gradientUnits="userSpaceOnUse">
  <stop offset="0" stop-color="#8ff7e4"/><stop offset=".38" stop-color="#27d1bd"/><stop offset=".78" stop-color="#0f8f9c"/><stop offset="1" stop-color="#0a5f78"/>
</radialGradient>
<radialGradient id="kqGloss" cx=".5" cy=".5" r=".5">
  <stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
</radialGradient>
<radialGradient id="kqShadow" cx=".5" cy=".5" r=".5">
  <stop offset="0" stop-color="#021018" stop-opacity=".55"/><stop offset="1" stop-color="#021018" stop-opacity="0"/>
</radialGradient>
<radialGradient id="kqEyeGlow" cx=".5" cy=".5" r=".5">
  <stop offset="0" stop-color="#ffc24a" stop-opacity=".55"/><stop offset="1" stop-color="#ffc24a" stop-opacity="0"/>
</radialGradient>
<radialGradient id="kqIris" cx=".4" cy=".35" r=".75">
  <stop offset="0" stop-color="#fff1a8"/><stop offset=".45" stop-color="#fbbf24"/><stop offset="1" stop-color="#d97706"/>
</radialGradient>
"""


def background_svg(rx=116):
    """Fond de l'icône : carré arrondi, halo, grille de graphique très discrète, bulles."""
    g = []
    g.append('<rect width="512" height="512" rx="%d" fill="url(#kqBg)"/>' % rx)
    g.append('<rect width="512" height="512" rx="%d" fill="url(#kqGlow)"/>' % rx)
    # grille de graphique (clin d'œil quant)
    lines = []
    for i in range(1, 8):
        lines.append('<path d="M0,%d H512"/>' % (i * 64))
        lines.append('<path d="M%d,0 V512"/>' % (i * 64))
    g.append('<clipPath id="kqClip"><rect width="512" height="512" rx="%d"/></clipPath>' % rx)
    g.append('<g clip-path="url(#kqClip)" stroke="#9fe8ff" stroke-opacity=".045" stroke-width="1">%s</g>' % "".join(lines))
    # bulles
    for x, y, r in ((74, 96, 7), (96, 150, 4), (440, 120, 8), (418, 70, 4.5), (452, 186, 3.5), (58, 220, 3.2)):
        g.append('<circle cx="%d" cy="%d" r="%s" fill="none" stroke="#7ff0e0" stroke-opacity=".35" stroke-width="2"/>' % (x, y, r))
    # liseré intérieur
    if rx:
        g.append('<rect x="2" y="2" width="508" height="508" rx="%d" fill="none" stroke="#bff5ff" stroke-opacity=".10" stroke-width="2"/>' % (rx - 2))
    return "\n".join(g)


def svg_doc(inner, defs="", title="KrakenQ"):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="%s">\n'
        "<title>%s</title>\n<defs>%s</defs>\n%s\n</svg>\n" % (title, title, defs, inner)
    )


def build(outdir):
    os.makedirs(outdir, exist_ok=True)
    body, right, left = kraken_group(True)
    tf = fit_transform(right, left)

    icon = background_svg() + '\n<g transform="%s">\n%s\n</g>' % (tf, body)
    mark = '<g transform="%s">\n%s\n</g>' % (tf, body)

    bleed = background_svg(0) + '\n<g transform="%s">\n%s\n</g>' % (fit_transform(right, left, 330, 338, 268), body)
    tight = (
        '<rect width="512" height="512" rx="104" fill="url(#kqBg)"/><rect width="512" height="512" rx="104" fill="url(#kqGlow)"/>'
        '\n<g transform="%s">\n%s\n</g>' % (fit_transform(right, left, 468, 470, 268), body)
    )
    mono_body, _, _ = kraken_group(False)
    mono = (
        '<mask id="kqMask" maskUnits="userSpaceOnUse" x="0" y="0" width="512" height="512">'
        '<g transform="%s">\n%s\n</g></mask>'
        '<rect width="512" height="512" fill="currentColor" mask="url(#kqMask)"/>' % (tf, mono_body)
    )

    files = {
        "logo.svg": svg_doc(icon, DEFS_COLOUR, "KrakenQ"),
        "logo-mark.svg": svg_doc(mark, DEFS_COLOUR, "KrakenQ"),
        "logo-fullbleed.svg": svg_doc(bleed, DEFS_COLOUR, "KrakenQ"),
        "logo-tight.svg": svg_doc(tight, DEFS_COLOUR, "KrakenQ"),
        "logo-mono.svg": svg_doc(mono, "", "KrakenQ"),
    }
    for name, content in files.items():
        with open(os.path.join(outdir, name), "w", encoding="utf-8") as f:
            f.write(content)
        print("écrit", os.path.join(outdir, name), "(%d Ko)" % (len(content) // 1024 + 1))


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
