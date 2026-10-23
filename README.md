# 🐙 KrakenQ

Prototype éducatif d'assistant IA dédié au **développement quantitatif** (APIs d'exchanges, backtesting, gestion du risque, bots Python).

---

## 📸 Aperçu & Fonctionnalités

### 1. Interface de Chat & Mode Hors-Ligne (Fallback)
Même en cas d'erreur de clé API ou sans connexion, KrakenQ continue de répondre grâce à sa **base de connaissances intégrée** :

<p align="center">
  <img src="assets/chat-fallback.jpg" width="45%" alt="Erreur API et bascule hors-ligne">
  <img src="assets/chat-offline.jpg" width="45%" alt="Réponse du mode hors-ligne">
</p>

### 2. Support Multi-IA & Clés API Personnalisées
Tu peux configurer tes propres clés API (Claude / Anthropic, OpenAI, Groq, OpenRouter) ou pointer vers un serveur local (Ollama) :

<p align="center">
  <img src="assets/config-api1.jpg" width="45%" alt="Réglages Claude">
  <img src="assets/config-api2.jpg" width="45%" alt="Réglages OpenAI et serveurs locaux">
</p>

---

## 🚀 Lancement rapide sur Termux

```bash
pkg install python unzip
termux-setup-storage
cp ~/storage/downloads/krakenq.zip ~ && cd ~ && unzip krakenq.zip && cd krakenq
python app.py

