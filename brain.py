"""Cerveau de KrakenQ : consigne système + mini base de connaissances Quant dev.

Deux rôles :
  1. SYSTEM_PROMPT   : la « spécialisation » envoyée au modèle (Claude, OpenAI, Groq, Ollama…).
  2. answer()        : un cerveau hors-ligne (aucune clé, aucun réseau) qui répond aux questions
                       classiques d'un quant dev à partir de la base KB ci-dessous.

Pour enseigner quelque chose de nouveau au mode hors-ligne, ajoute une entrée dans KB :
    dict(id=..., strong=[mots-clés précis], weak=[mots-clés larges], title=..., text="markdown")
"""
import re
import unicodedata

SYSTEM_PROMPT = """Tu es Kraken, un assistant IA spécialisé en développement quantitatif (quant dev) : trading algorithmique, \
données de marché, backtesting, APIs d'exchanges (REST / WebSocket), gestion du risque, architecture de systèmes de trading, \
performance Python (numpy, pandas, numba, asyncio) et statistiques appliquées à la finance.

Règles :
- Réponds dans la langue de l'utilisateur (français par défaut), avec un ton clair, concret et pédagogue.
- Commence par la réponse directe en 1 à 3 phrases, puis détaille seulement ce qui est utile.
- Donne des exemples de code Python courts, exécutables et commentés. Préfère la bibliothèque standard ou des dépendances légères : l'utilisateur travaille souvent sur mobile (Termux).
- Signale les pièges classiques : look-ahead bias, survivorship bias, overfitting, frais et slippage, limites de débit, sécurité des clés API, fuseaux horaires.
- Ne promets jamais de gains et ne donne pas de conseil d'investissement personnalisé ; rappelle brièvement le risque quand c'est pertinent.
- Si la question est floue, fais l'hypothèse la plus raisonnable et dis-la, ou pose UNE seule question de clarification.
- Ne demande jamais de clé API, de mot de passe ou de secret dans la conversation.
- Mets en forme en Markdown : titres courts, listes quand elles aident, blocs de code avec le langage."""

# --------------------------------------------------------------------------------------
# Base de connaissances hors-ligne
# --------------------------------------------------------------------------------------

KB = [
    dict(
        id="api",
        title="C'est quoi une API ?",
        strong=["quoi une api", "qu est ce qu une api", "qu est ce qu'une api", "definition api", "definition d une api", "expliquer api"],
        weak=["api", "apis", "interface de programmation"],
        text="""**Une API** (*Application Programming Interface*) est la porte d'entrée officielle qu'un service ouvre aux programmes. \
Au lieu de cliquer sur un site, ton code envoie une **requête** et reçoit une **réponse** dans un format lisible par une machine (le plus souvent du JSON).

En trading, la plateforme d'échange expose une API pour :
1. **lire** des données (prix, carnet d'ordres, bougies) ;
2. **passer ou annuler** des ordres ;
3. **consulter** ton solde et tes positions.

Ton script Python devient le « client » de cette API :

```python
import json
import urllib.request

url = "https://api.exchange.example/v1/ticker?symbol=BTCUSDT"   # adresse fictive
with urllib.request.urlopen(url, timeout=10) as r:
    data = json.load(r)
print(data["price"])
```

**À retenir pour un quant dev**
- **REST** : une requête → une réponse (historique, ordres). **WebSocket** : flux continu en temps réel (prix, carnet).
- Les endpoints **publics** (données de marché) n'ont pas besoin de clé ; les endpoints **privés** (solde, ordres) demandent une **clé API** et une signature.
- Chaque API a des **limites de débit** : trop de requêtes → erreur `429`.
- Garde tes clés secrètes (variables d'environnement, jamais dans le code) et donne-leur le minimum de droits : lecture seule pour tester, **jamais le droit de retrait**.

Pour creuser : *REST vs WebSocket*, *sécurité des clés API*, *rate limit*.""",
    ),
    dict(
        id="rest-ws",
        title="REST vs WebSocket",
        strong=["rest vs websocket", "rest ou websocket", "difference rest websocket", "websocket"],
        weak=["rest", "temps reel", "streaming", "polling"],
        text="""**REST** et **WebSocket** servent deux besoins différents :

| | REST | WebSocket |
|---|---|---|
| Modèle | question → réponse | connexion ouverte, le serveur pousse les données |
| Idéal pour | historique, solde, passer un ordre | prix en direct, carnet d'ordres, exécutions |
| Latence | une requête à chaque fois | très faible une fois connecté |
| Limite de débit | vite atteinte si tu « pollues » | beaucoup plus économe |
| Piège | polling trop fréquent → `429` | déconnexions : il faut **se reconnecter** et resynchroniser |

**Règle pratique :** WebSocket pour *écouter* le marché, REST pour *agir* (ordres) et récupérer l'historique.

```python
# Squelette de boucle WebSocket robuste (pip install websockets)
import asyncio, json, websockets

async def ecouter(url, sub):
    delai = 1
    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                await ws.send(json.dumps(sub))
                delai = 1
                async for msg in ws:
                    traiter(json.loads(msg))
        except Exception as e:
            print("coupure :", e, "→ reconnexion dans", delai, "s")
            await asyncio.sleep(delai)
            delai = min(delai * 2, 30)   # backoff exponentiel
```""",
    ),
    dict(
        id="cle-api",
        title="Sécuriser ses clés API",
        strong=["cle api", "cles api", "clef api", "api key", "securiser cle", "secret api", "signature hmac", "hmac"],
        weak=["cle", "secret", "env", "whitelist", "permissions"],
        text="""Une clé API de trading = l'accès à ton argent. Les bonnes pratiques :

1. **Jamais dans le code ni sur GitHub.** Utilise des variables d'environnement ou un fichier `.env` listé dans `.gitignore`.
2. **Droits minimaux** : lecture seule pour développer ; « trading » seulement si nécessaire ; **retrait toujours désactivé**.
3. **Liste blanche d'IP** quand la plateforme le permet.
4. **Une clé par projet**, à renouveler régulièrement, et à révoquer au moindre doute.
5. **Teste sur un testnet / compte de démo** avant de passer en réel.
6. **Ne colle jamais une clé dans un chat**, une capture d'écran ou un log.

```python
import os, hmac, hashlib, time

KEY = os.environ["EXCHANGE_KEY"]          # lues depuis l'environnement
SECRET = os.environ["EXCHANGE_SECRET"]

def signer(params: str) -> str:
    # La plupart des exchanges demandent une signature HMAC-SHA256 de la requête
    return hmac.new(SECRET.encode(), params.encode(), hashlib.sha256).hexdigest()

query = f"symbol=BTCUSDT&timestamp={int(time.time() * 1000)}"
print(query + "&signature=" + signer(query))
```""",
    ),
    dict(
        id="rate-limit",
        title="Limites de débit et erreurs 429",
        strong=["rate limit", "rate limiting", "limite de debit", "limites de debit", "erreur 429", "429", "backoff"],
        weak=["debit", "throttle", "requetes par seconde", "ban ip"],
        text="""Les exchanges plafonnent le nombre de requêtes (ex. N par minute ou un « poids » par endpoint). Au-delà : erreur **429** et parfois un bannissement temporaire d'IP.

**Comment rester dans les clous**
- Lis les en-têtes de réponse (`Retry-After`, poids restant) quand ils existent.
- Remplace le *polling* REST par un flux **WebSocket**.
- Mets en **cache** ce qui change peu (liste des marchés, frais).
- Applique un **backoff exponentiel avec jitter** après chaque `429` / `5xx`.

```python
import random, time, urllib.request, urllib.error

def appeler(url, essais=6):
    for n in range(essais):
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504):
                raise
            attente = float(e.headers.get("Retry-After", 2 ** n)) + random.random()
            time.sleep(attente)
    raise RuntimeError("trop d'échecs")
```""",
    ),
    dict(
        id="ohlcv",
        title="Bougies OHLCV",
        strong=["ohlcv", "bougie", "bougies", "candlestick", "chandelier", "chandeliers", "klines", "kline"],
        weak=["open high low close", "timeframe", "resample", "unite de temps"],
        text="""Une **bougie** (candlestick) résume le prix sur une période : **O**pen (ouverture), **H**igh (plus haut), **L**ow (plus bas), **C**lose (clôture) et **V**olume. On parle d'**OHLCV**.

```python
import pandas as pd

df = pd.read_csv("btc_1m.csv", parse_dates=["time"], index_col="time")   # colonnes : open high low close volume
h1 = df.resample("1h").agg({"open": "first", "high": "max", "low": "min",
                            "close": "last", "volume": "sum"}).dropna()
```

**Pièges**
- Travaille en **UTC** et garde les horodatages cohérents.
- La **dernière bougie n'est pas terminée** : ne décide jamais sur une bougie en cours (c'est un *look-ahead bias* déguisé).
- Vérifie les **trous** dans les données (maintenance, coupures) avant de calculer quoi que ce soit.""",
    ),
    dict(
        id="donnees",
        title="Récupérer des données historiques",
        strong=["donnees historiques", "historique de prix", "telecharger des donnees", "recuperer des donnees", "pagination"],
        weak=["donnees", "dataset", "csv", "parquet", "sqlite"],
        text="""Trois sources courantes : l'**API REST de l'exchange** (bougies par pages), des **fichiers CSV/Parquet** publiés par la plateforme, ou une base que tu alimentes toi-même avec un flux WebSocket.

**Méthode propre**
1. Pagine par *timestamp* (`startTime` → dernière bougie reçue + 1) en respectant le rate limit.
2. Supprime les doublons, trie par temps, vérifie qu'il n'y a pas de trous.
3. Stocke en **Parquet** ou **SQLite** (léger, parfait sur mobile) plutôt qu'en CSV géants.
4. Garde les données brutes **immuables** ; fais tes calculs sur une copie.

```python
import sqlite3
db = sqlite3.connect("marche.db")
db.execute("CREATE TABLE IF NOT EXISTS bougies("
           "symbole TEXT, t INTEGER, o REAL, h REAL, l REAL, c REAL, v REAL, "
           "PRIMARY KEY (symbole, t))")
db.executemany("INSERT OR IGNORE INTO bougies VALUES (?,?,?,?,?,?,?)", lignes)
db.commit()
```""",
    ),
    dict(
        id="backtest",
        title="Faire un backtest",
        strong=["backtest", "backtesting", "back test", "tester une strategie", "tester ma strategie"],
        weak=["strategie", "simulation", "historique"],
        text="""Un **backtest** rejoue ta stratégie sur des données passées pour estimer ce qu'elle aurait fait. Il ne *prouve* rien : il sert surtout à éliminer les mauvaises idées.

**Squelette vectorisé minimal (pandas)**
```python
import numpy as np, pandas as pd

px = df["close"]
ret = px.pct_change()
signal = (px.rolling(20).mean() > px.rolling(100).mean()).astype(int)   # 1 = long, 0 = hors marché
position = signal.shift(1)              # IMPORTANT : on agit à la bougie SUIVANTE
frais = position.diff().abs() * 0.001   # 0,1 % par changement de position
perf = (position * ret - frais).fillna(0)
equity = (1 + perf).cumprod()
```

**Checklist**
- `shift(1)` sur le signal → sinon tu triches avec le futur.
- Inclure **frais, spread et slippage** (souvent ce qui tue une stratégie).
- Séparer **entraînement / validation / test** et finir par du **walk-forward**.
- Regarder le **drawdown** et le nombre de trades, pas seulement le rendement.""",
    ),
    dict(
        id="biais",
        title="Biais et overfitting",
        strong=["overfitting", "surapprentissage", "look ahead", "lookahead", "survivorship", "biais", "data snooping", "walk forward", "out of sample"],
        weak=["sur optimisation", "optimisation de parametres", "robustesse", "validation"],
        text="""Les erreurs qui font briller un backtest… et perdre en réel :

- **Look-ahead bias** : utiliser une information pas encore connue (bougie non clôturée, signal non décalé, normalisation sur tout le jeu de données).
- **Survivorship bias** : ne tester que les actifs qui existent encore aujourd'hui.
- **Overfitting / data snooping** : tester 500 paramètres et garder le meilleur — c'est du bruit qui ressemble à un signal.
- **Coûts irréalistes** : frais, spread, slippage et latence oubliés.

**Antidotes**
1. Peu de paramètres, une **logique économique** claire avant de tester.
2. Découpage **train / validation / test**, test touché **une seule fois**.
3. **Walk-forward** : optimiser sur une fenêtre, valider sur la suivante, faire glisser.
4. Vérifier que les résultats tiennent quand on **perturbe** légèrement les paramètres (zone stable, pas un pic isolé).
5. Se méfier d'un Sharpe trop beau : si ça paraît trop facile, c'est probablement un bug.""",
    ),
    dict(
        id="metriques",
        title="Sharpe, drawdown & co",
        strong=["sharpe", "sortino", "calmar", "drawdown", "profit factor", "ratio de sharpe", "metriques de performance"],
        weak=["performance", "rendement ajuste", "volatilite annualisee", "equity"],
        text="""Les indicateurs à regarder ensemble :

- **Sharpe** = rendement moyen excédentaire / écart-type, annualisé. Repère : < 1 faible, 1–2 correct, > 3 suspect.
- **Sortino** : comme Sharpe mais ne pénalise que la volatilité à la baisse.
- **Max drawdown** : pire chute depuis un sommet. C'est ce que tu devras *supporter* psychologiquement et financièrement.
- **Calmar** = rendement annuel / max drawdown.
- **Profit factor** = gains bruts / pertes brutes ; **taux de réussite** et **gain moyen / perte moyenne**.

```python
import numpy as np

def sharpe(r, periodes_par_an=365):         # crypto : 365 (24/7) ; actions : ~252
    return np.sqrt(periodes_par_an) * r.mean() / r.std(ddof=1)

def max_drawdown(equity):
    pic = equity.cummax()
    return (equity / pic - 1).min()          # nombre négatif, ex. -0.27 = -27 %
```""",
    ),
    dict(
        id="sizing",
        title="Taille de position",
        strong=["position sizing", "taille de position", "kelly", "risque par trade", "volatility targeting", "levier"],
        weak=["sizing", "taille", "capital", "mise"],
        text="""La **taille de position** compte souvent plus que le signal.

1. **Risque fixe par trade** : risquer ~0,5–1 % du capital. `taille = (capital × risque%) / (prix_entrée − prix_stop)`.
2. **Ciblage de volatilité** : plus l'actif est volatil, plus la position est petite → risque comparable d'un trade à l'autre.
3. **Kelly** : `f* = p − (1 − p)/b` (p = taux de réussite, b = gain moyen / perte moyenne). Le Kelly complet est agressif et très sensible aux erreurs d'estimation : on utilise au mieux **¼ à ½ Kelly**.

```python
def taille(capital, risque_pct, entree, stop):
    risque_unitaire = abs(entree - stop)
    return capital * risque_pct / risque_unitaire

print(taille(1000, 0.01, 60000, 58800))   # ≈ 0.0083 BTC
```
Le **levier** n'augmente pas l'avantage statistique, il amplifie surtout les pertes et le risque de liquidation.""",
    ),
    dict(
        id="frais",
        title="Frais, spread et slippage",
        strong=["slippage", "frais de trading", "spread", "maker taker", "impact de marche", "couts de transaction"],
        weak=["frais", "commission", "maker", "taker", "couts"],
        text="""Les coûts d'exécution sont la première cause d'écart entre backtest et réel :

- **Frais** : *maker* (tu ajoutes de la liquidité avec un ordre limite) en général moins chers que *taker* (tu consommes la liquidité).
- **Spread** : écart entre meilleur achat (bid) et meilleure vente (ask). Un aller-retour « au marché » coûte au moins un spread.
- **Slippage** : écart entre le prix espéré et le prix obtenu, surtout sur gros ordres ou marchés peu liquides.
- **Impact de marché** : ton propre ordre fait bouger le prix.

**Règle de prudence** : dans un backtest, retire au minimum `frais + demi-spread + une marge de slippage` à **chaque** exécution, et stresse ces valeurs (×2) pour voir si la stratégie survit.

```python
cout_aller_retour = 2 * (0.0004 + 0.0002 + 0.0003)   # frais + demi-spread + slippage, par côté
```""",
    ),
    dict(
        id="carnet",
        title="Carnet d'ordres",
        strong=["carnet d ordres", "carnet d'ordres", "order book", "orderbook", "bid ask", "profondeur de marche", "liquidite"],
        weak=["carnet", "bid", "ask", "mid price", "imbalance", "depth"],
        text="""Le **carnet d'ordres** liste les ordres limites en attente :
- **Bids** : acheteurs (du plus haut prix vers le bas) ; **Asks** : vendeurs (du plus bas vers le haut).
- **Spread** = meilleur ask − meilleur bid ; **mid-price** = (bid + ask) / 2.
- **Profondeur** : quantité disponible à chaque niveau — elle dit combien tu peux acheter/vendre sans trop bouger le prix.
- **Déséquilibre** (imbalance) : `(vol_bid − vol_ask) / (vol_bid + vol_ask)` — indicateur court terme classique.

```python
def imbalance(bids, asks, niveaux=5):
    vb = sum(q for _, q in bids[:niveaux])
    va = sum(q for _, q in asks[:niveaux])
    return (vb - va) / (vb + va)
```
Via WebSocket, on reçoit un *snapshot* puis des **mises à jour incrémentales** : il faut les appliquer dans l'ordre et resynchroniser en cas de trou.""",
    ),
    dict(
        id="ordres",
        title="Types d'ordres",
        strong=["types d ordres", "types d'ordres", "ordre limite", "ordre au marche", "stop loss", "stop limit", "post only", "ioc", "fok"],
        weak=["ordre", "ordres", "limit", "market", "stop"],
        text="""- **Market** : exécuté tout de suite au meilleur prix disponible (rapide, mais slippage et frais *taker*).
- **Limit** : exécuté seulement à ton prix ou mieux (peut ne jamais se remplir).
- **Stop / stop-loss** : se déclenche quand le prix franchit un seuil ; **stop-limit** déclenche un ordre limite (risque de non-exécution).
- **Post-only** : refusé s'il devait être exécuté immédiatement → garantit d'être *maker*.
- **IOC / FOK** : *Immediate-Or-Cancel* (remplit ce qui peut l'être, annule le reste) / *Fill-Or-Kill* (tout ou rien).
- **Reduce-only** : ne peut que réduire une position existante (sécurité sur les dérivés).

**Bon réflexe API :** envoie toujours un **identifiant client unique** (`clientOrderId`) pour pouvoir retrouver l'ordre et éviter les doublons après une coupure réseau.""",
    ),
    dict(
        id="pandas",
        title="Vectoriser avec numpy / pandas",
        strong=["vectoriser", "vectorisation", "pandas", "numpy", "numba", "iterrows", "performance python"],
        weak=["dataframe", "boucle", "rolling", "ewm", "lent"],
        text="""Python pur est lent en boucle ; numpy/pandas déportent le calcul dans du code compilé.

```python
# ❌ lent
for i in range(1, len(df)):
    df.loc[df.index[i], "ret"] = df["close"].iloc[i] / df["close"].iloc[i - 1] - 1

# ✅ vectorisé
df["ret"] = df["close"].pct_change()
df["sma20"] = df["close"].rolling(20).mean()
df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
df["vol"] = df["ret"].rolling(30).std() * (365 ** 0.5)
```

**Conseils**
- Bannis `iterrows()` ; pense `shift`, `rolling`, `ewm`, `groupby`, opérations sur colonnes entières.
- Travaille en `float64`, évite de copier inutilement de gros DataFrames.
- Si une boucle est inévitable (logique d'état), essaie **numba** (`@njit`).
- Sur Termux, installe numpy via `pkg install python-numpy` (les paquets précompilés passent mieux que `pip` qui compile).""",
    ),
    dict(
        id="strategies",
        title="Familles de stratégies",
        strong=["mean reversion", "momentum", "market making", "arbitrage", "pairs trading", "breakout", "retour a la moyenne", "familles de strategies"],
        weak=["tendance", "cointegration", "stat arb", "scalping"],
        text="""Les grandes familles, à connaître avant d'inventer quoi que ce soit :

- **Suivi de tendance / momentum** : acheter ce qui monte, vendre ce qui baisse (moyennes mobiles, breakout). Gagne peu souvent mais gros ; souffre en marché sans direction.
- **Retour à la moyenne** : parier qu'un écart excessif se résorbe (bandes de Bollinger, z-score). Beaucoup de petits gains, risque de grosse perte si la tendance s'installe.
- **Pairs trading / stat arb** : trader l'écart entre deux actifs **cointégrés**.
- **Arbitrage** : exploiter un écart de prix entre places de marché ; vite écrasé par la latence et les frais.
- **Market making** : poser des ordres des deux côtés du carnet et gagner le spread ; demande une infra rapide et une gestion d'inventaire sérieuse.

```python
z = (px - px.rolling(50).mean()) / px.rolling(50).std()   # z-score : signal de retour à la moyenne
long_signal, short_signal = z < -2, z > 2
```""",
    ),
    dict(
        id="volatilite",
        title="Volatilité",
        strong=["volatilite", "volatility", "atr", "ecart type des rendements", "annualiser"],
        weak=["vol", "variance", "log returns", "rendements logarithmiques"],
        text="""La **volatilité** mesure l'amplitude des variations. La version la plus utilisée : l'écart-type des rendements, **annualisée**.

```python
import numpy as np

r = np.log(df["close"]).diff()                 # rendements logarithmiques
vol_annuelle = r.std(ddof=1) * np.sqrt(365)    # 365 pour la crypto (24/7), ~252 pour les actions
atr14 = (df["high"] - df["low"]).rolling(14).mean()   # ATR simplifié : amplitude moyenne en prix
```
Usages : dimensionner les positions, placer des stops proportionnels (ex. 2 × ATR), filtrer les régimes de marché. Attention : la volatilité est **persistante** (des périodes calmes puis agitées) — d'où les modèles type EWMA/GARCH.""",
    ),
    dict(
        id="architecture",
        title="Architecture d'un bot de trading",
        strong=["architecture", "event driven", "asyncio", "latence", "bot de trading", "systeme de trading"],
        weak=["bot", "modules", "queue", "reconnexion", "logs", "idempotence"],
        text="""Une architecture saine sépare quatre briques, reliées par des **files d'événements** :

1. **Données** : WebSocket/REST → normalisation → stockage.
2. **Stratégie** : reçoit des événements (nouvelle bougie, tick) et émet des *intentions* (« acheter 0,01 »).
3. **Risque** : valide chaque intention (taille max, perte du jour, données fraîches) — peut dire non.
4. **Exécution** : transforme en ordres, gère les erreurs, retries, états (envoyé / rempli / annulé).

**Principes utiles**
- La **même logique** tourne en backtest et en réel (seule la source des événements change).
- **Idempotence** : un ordre renvoyé après une coupure ne doit pas être doublé (`clientOrderId`).
- **Journalise tout** (décisions, ordres, réponses) avec horodatage UTC.
- Reconnexions automatiques, *heartbeat*, détection de données périmées.
- `asyncio` suffit largement pour un trader indépendant ; la latence ultra-basse est un autre métier.""",
    ),
    dict(
        id="risque",
        title="Gestion du risque et coupe-circuit",
        strong=["circuit breaker", "coupe circuit", "kill switch", "gestion du risque", "perte maximale", "var", "value at risk"],
        weak=["risque", "protection", "limite de perte", "securite du bot"],
        text="""Avant d'automatiser, mets des **garde-fous codés en dur**, indépendants de la stratégie :

- **Perte maximale du jour / de la semaine** → arrêt total.
- **Taille maximale** par ordre et par position (anti « fat finger »).
- **Données périmées** (dernier tick trop vieux) → pas de trading.
- **Trop d'erreurs d'API** d'affilée → pause.
- **Kill switch manuel** : un fichier ou une commande qui coupe tout.

```python
class CoupeCircuit:
    def __init__(self, perte_max_jour, ordre_max):
        self.perte_max_jour, self.ordre_max = perte_max_jour, ordre_max
        self.pnl_jour, self.arrete = 0.0, False

    def autoriser(self, taille_ordre):
        if self.arrete or taille_ordre > self.ordre_max:
            return False
        if self.pnl_jour <= -self.perte_max_jour:
            self.arrete = True          # verrouillé jusqu'à intervention humaine
        return not self.arrete
```
Mesure aussi la **VaR** (perte qui n'est dépassée que dans 1 ou 5 % des cas) : `np.percentile(rendements, 5)` pour une VaR historique à 95 %.""",
    ),
    dict(
        id="stack",
        title="Boîte à outils Python du quant dev",
        strong=["ccxt", "bibliotheques python", "librairies python", "outils quant", "vectorbt", "backtrader"],
        weak=["librairie", "bibliotheque", "outil", "framework", "stack"],
        text="""Un socle courant :

- **numpy**, **pandas** : calcul et séries temporelles. **scipy**, **statsmodels** : statistiques, régressions, cointégration.
- **numba** : accélérer les boucles. **scikit-learn** : modèles ML classiques (avec prudence : bruit énorme en finance).
- **ccxt** : interface unifiée pour des dizaines d'exchanges (REST, et WebSocket dans la version Pro).
- **websockets** / **aiohttp** : flux temps réel et requêtes asynchrones.
- **SQLite**, **Parquet** : stockage léger.
- **matplotlib** / **plotly** : graphiques ; backtests prêts à l'emploi : **backtesting.py**, **vectorbt**, **backtrader**.

Commence **simple** : un backtest vectorisé de 30 lignes que tu comprends à 100 % vaut mieux qu'un framework dont tu ignores les hypothèses.""",
    ),
    dict(
        id="termux",
        title="Travailler sous Termux",
        strong=["termux", "sur telephone", "sur mobile", "android"],
        weak=["pkg install", "tmux", "wake lock"],
        text="""Quelques réflexes pour développer et faire tourner des scripts de trading sur Android :

```bash
pkg update && pkg upgrade
pkg install python git tmux
termux-wake-lock          # empêche la mise en veille du processus
tmux new -s bot           # session qui survit à la fermeture de l'app
python app.py
```
- Désactive l'**optimisation de batterie** pour Termux dans les réglages Android, sinon le système tue le processus en arrière-plan.
- Préfère des dépendances **légères** (la bibliothèque standard va déjà très loin) ; numpy via `pkg install python-numpy`.
- Garde tes clés dans des variables d'environnement ou un `.env` privé, jamais dans un dossier partagé.
- Pour un bot réellement critique, un petit serveur (VPS) reste plus fiable qu'un téléphone.""",
    ),
    dict(
        id="qui",
        title="Qui es-tu ?",
        strong=["qui es tu", "tu es qui", "presente toi", "que sais tu faire"],
        weak=["bonjour", "salut", "hello", "aide", "help", "kraken", "merci"],
        text="""Je suis **Kraken**, ton assistant spécialisé en **développement quantitatif** : APIs d'exchanges, données de marché, backtesting, gestion du risque, architecture de bots et performance Python.

Essaie par exemple :
- *C'est quoi une API ?*
- *REST ou WebSocket ?*
- *Comment faire un backtest sans me tromper ?*
- *Explique le Sharpe et le drawdown.*
- *Comment sécuriser mes clés API ?*
- *Comment calculer la taille de position ?*

Je suis un **projet fun** : un prototype éducatif, pas un conseil d'investissement. Je ne passe aucun ordre.

Je fonctionne ici en **mode hors-ligne** (base de connaissances intégrée). Dans ⚙️ **Réglages**, ajoute une clé API (Claude, OpenAI, ou tout service compatible) pour obtenir des réponses libres, adaptées à ton code.""",
    ),
]

# --------------------------------------------------------------------------------------
# Moteur de correspondance
# --------------------------------------------------------------------------------------


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _hit(keyword: str, norm_text: str) -> bool:
    k = normalize(keyword)
    return bool(k) and re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?:s|x)?(?![a-z0-9])", norm_text) is not None


def best_entries(text: str, limit: int = 3):
    norm = normalize(text)
    scored = []
    for e in KB:
        score = 4 * sum(_hit(k, norm) for k in e["strong"]) + 2 * sum(_hit(k, norm) for k in e["weak"])
        if score:
            scored.append((score, e))
    scored.sort(key=lambda s: -s[0])
    return scored[:limit]


def answer(messages) -> str:
    """messages : liste de {role, content}. Répond à la dernière question de l'utilisateur."""
    last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    ranked = best_entries(last)
    if ranked and ranked[0][0] >= 2:
        top = ranked[0][1]
        reply = top["text"]
        others = [e for s, e in ranked[1:] if s >= 2]
        if others:
            reply += "\n\n**Voir aussi :** " + " · ".join("*%s*" % e["title"] for e in others)
        return reply
    menu = "\n".join("- *%s*" % e["title"] for e in KB if e["id"] != "qui")
    return (
        "Je n'ai pas de réponse précise à cette question en **mode hors-ligne**.\n\n"
        "Voici les sujets que je maîtrise sans connexion :\n\n%s\n\n"
        "Pour poser n'importe quelle question (et obtenir du code sur mesure), ajoute une clé API dans ⚙️ **Réglages**."
        % menu
    )
