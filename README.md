# KrakenQ — projet fun

> ⚠️ **Projet fun : prototype éducatif, créé en solo.**
>
> **À ne pas utiliser pour investir de l'argent réel.** KrakenQ explique des notions de développement quantitatif et aide à écrire du code. Il ne passe aucun ordre, ne se connecte à aucune plateforme d'échange et ne donne aucun conseil financier.
>
> Ses réponses peuvent être fausses ou incomplètes, il n'a fait l'objet d'aucune validation sérieuse et il est fourni « tel quel », sans garantie (voir `LICENSE`).
>
> Tant que son auteur ne l'a pas repris au sérieux (relecture, tests, limites documentées), considère-le comme un jouet. Même alors, trader comporte un risque de perte totale du capital.
>
> *English: fun project, educational prototype built solo. Not financial advice, not for real-money investing. Provided as is, without warranty.*
>
> Le nom vient du monstre marin : KrakenQ n'a aucun lien avec la plateforme d'échange Kraken.

Petite IA spécialisée **Quant dev** : une page web locale avec des **conversations en onglets**.
Un seul script Python (`app.py`), aucune dépendance à installer.

Au tout premier lancement, le premier onglet pose pour toi la question **« C'est quoi une API ? »**.

## Démarrer

**Termux (Android)**

```bash
pkg install python unzip
termux-setup-storage                       # une seule fois : accès au dossier Téléchargements
cp ~/storage/downloads/krakenq.zip ~ && cd ~ && unzip krakenq.zip && cd krakenq
python app.py
```

**PC (Windows, Mac, Linux)** : décompresse le ZIP, ouvre un terminal dans le dossier, puis `python app.py`.

L'interface s'ouvre toute seule ; sinon va sur **http://127.0.0.1:8787** dans le navigateur.
`./start.sh` fait la même chose et empêche la mise en veille sous Termux.

## Utiliser les onglets

- **+** crée une conversation indépendante ; **×** la ferme ; **double-clic** sur un titre la renomme.
- Tu peux lancer des questions dans plusieurs onglets en même temps. Le point de l'onglet pulse pendant la réponse, puis devient ambre si la réponse est prête dans un onglet que tu n'as pas ouvert.
- **Entrée** envoie (Maj+Entrée = nouvelle ligne). Sur téléphone, Entrée fait un retour à la ligne et la flèche envoie.
- Le bouton carré arrête une réponse en cours.
- Les onglets sont gardés dans le navigateur : tu les retrouves au prochain lancement.

## Choisir qui répond

Ouvre **⚙️ Réglages** (la pastille en haut à droite) :

| Cerveau | Ce qu'il faut |
|---|---|
| **Hors-ligne** (par défaut) | rien : la base de connaissances intégrée (`brain.py`) répond aux questions Quant dev classiques |
| **Claude** | une clé API Anthropic (modèle par défaut : `claude-haiku-5-5`, modifiable) |
| **Compatible OpenAI** | une adresse d'API + un modèle (+ une clé) : OpenAI, Groq, OpenRouter, Mistral, ou un serveur local (Ollama, llama.cpp) |

Tu peux aussi copier `.env.example` en `.env` et y mettre `ANTHROPIC_API_KEY=...` : `.env` et les variables d'environnement l'emportent sur les Réglages.
Si le service en ligne échoue (réseau, quota, clé refusée), KrakenQ répond quand même avec le mode hors-ligne et te dit pourquoi.

Test rapide sans navigateur : `python app.py --ask "C'est quoi une API ?"`

## Personnaliser

- **Spécialisation** : la consigne envoyée au modèle est `SYSTEM_PROMPT` dans `brain.py`.
- **Mode hors-ligne** : ajoute une entrée dans la liste `KB` de `brain.py` (mots-clés + réponse en Markdown).
- **Questions de démarrage** et **première question** : `STARTERS` et `FIRST_QUESTION` en haut de `web/app.js`.
- **Nom du modèle, longueur des réponses** : Réglages.

## Le logo (dossier `brand/`)

Un kraken à 8 tentacules, sans texte, dessiné en SVG.

| Fichier | Usage |
|---|---|
| `logo.svg`, `logo-1024.png`, `logo-512.png` | icône complète (fond arrondi) |
| `logo-mark.svg`, `logo-mark-1024.png` | kraken seul, fond transparent |
| `logo-mono.svg`, `logo-mono-white-1024.png`, `logo-mono-dark-1024.png` | une seule couleur (tampon, impression, fond clair ou sombre) |
| `logo-fullbleed.svg`, `apple-touch-icon.png`, `icon-maskable-512.png` | icônes plein cadre (écran d'accueil du téléphone) |
| `logo-tight.svg`, `favicon.ico`, `favicon-32.png`, `icon-192.png` | très petites tailles |
| `build_logo.py` | régénère les SVG ; change un angle, une longueur ou l'enroulement d'un tentacule dans `TENTACLES` |

Astuce : dans Chrome sur Android, menu ⋮ puis **Ajouter à l'écran d'accueil** pour lancer KrakenQ comme une appli (le serveur doit tourner dans Termux).

## Peut-on l'utiliser pour de vrai ?

- **Pour apprendre, comprendre un concept, brainstormer du code : oui.** C'est son rôle.
- **Pour décider d'un investissement ou piloter un vrai compte : non.** Le mode hors-ligne est une base de résumés écrits à la main, sans données de marché en direct ; un modèle en ligne peut se tromper avec aplomb ; les extraits de code sont des exemples simplifiés (adresses fictives, formules de base).
- KrakenQ ne peut pas perdre d'argent tout seul : il ne détient aucune clé d'exchange et n'envoie aucun ordre. Le risque vient de ce qu'on fait de ses réponses. Toute idée de stratégie se vérifie d'abord par soi-même, en simulation (testnet, compte de démonstration), avec des montants que l'on peut se permettre de perdre.

## Sécurité

- Le serveur n'écoute que sur **127.0.0.1** : seul cet appareil y accède. Il refuse les requêtes venues d'autres sites.
- Les clés sont lues côté serveur, enregistrées dans `config.json` (droits 600) et envoyées uniquement au fournisseur choisi. Elles ne reviennent jamais dans le navigateur.
- `--host 0.0.0.0` ouvre l'accès à ton réseau Wi-Fi **sans mot de passe** : à éviter sur un réseau partagé.
- Ne colle jamais une clé API dans une conversation. Kraken ne t'en demandera pas.
- KrakenQ explique et aide à coder ; il ne donne pas de conseil d'investissement.

## Dépannage

- **« Serveur injoignable »** : `python app.py` n'est plus lancé (Termux l'a peut-être arrêté en arrière-plan). Relance-le, et désactive l'optimisation de batterie pour Termux.
- **Port occupé** : le port suivant est essayé automatiquement ; l'adresse exacte s'affiche au démarrage. Sinon `python app.py --port 9000`.
- **Clé refusée (401)** : recopie la clé dans les Réglages, ou efface-la avec « Effacer la clé enregistrée ».
- **Modèle introuvable (404)** : corrige le nom du modèle dans les Réglages.

## English summary

KrakenQ is a fun, educational prototype built solo: a tiny Quant-dev assistant with tabbed chats, a local Python server (standard library only) and a hand-drawn 8-tentacle kraken logo. It answers from a built-in knowledge base or, if you add a key, from Claude or any OpenAI-compatible API. It does not trade, holds no exchange credentials and is **not financial advice**. Do not use it to invest real money. Provided as is, MIT licence.
