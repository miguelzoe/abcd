# Cartronic — Intégration des appels vocaux internes WebRTC

## Objectif

Cette version remplace la simple ouverture du composeur téléphonique par un vrai module d’appel vocal interne à l’application : client et technicien peuvent s’appeler via Internet depuis Cartronic.

## Backend Django

Ajout d’une application `apps.voice_calls` :

- `VoiceCallSession` : session d’appel entre client et technicien, liée à une réservation.
- `VoiceCallSignal` : historique des signaux WebRTC échangés.
- API REST :
  - `POST /api/voice-calls/` : démarrer un appel depuis une réservation.
  - `POST /api/voice-calls/{id}/accept/` : accepter.
  - `POST /api/voice-calls/{id}/reject/` : refuser.
  - `POST /api/voice-calls/{id}/end/` : terminer.
  - `POST /api/voice-calls/{id}/missed/` : marquer comme manqué.
  - `POST /api/voice-calls/{id}/signal/` : fallback REST de signalisation.
  - `GET /api/voice-calls/history/` : historique.
  - `GET /api/voice-calls/ice-config/` : configuration STUN/TURN.
- WebSocket :
  - `/ws/voice/user/?token=<jwt>` : présence utilisateur et appels entrants.
  - `/ws/voice/calls/<session_id>/?token=<jwt>` : salon de signalisation WebRTC.
- Notifications internes et push pour appel entrant.
- Passage du serveur de `gunicorn`/WSGI à `daphne`/ASGI pour supporter les WebSockets.

## Mobile Expo / React Native

Ajouts principaux :

- `services/voice-call.service.ts` : service d’appel vocal.
- `components/voice/VoiceCallButton.tsx` : bouton réutilisable d’appel interne.
- `context/VoiceCallContext.tsx` : écoute des appels entrants en temps réel.
- `app/voice-call/[sessionId].tsx` : écran d’appel entrant/sortant.
- Intégration des boutons d’appel dans :
  - suivi client ;
  - détail mission technicien ;
  - chat client ;
  - chat technicien.
- Gestion micro, muet, haut-parleur, acceptation, refus, fin d’appel.
- Permissions micro iOS/Android ajoutées.

## Déploiement requis

### Backend

Après déploiement :

```bash
pip install -r requirements.txt
python manage.py migrate
```

Le serveur doit démarrer en ASGI :

```bash
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

En production multi-instance, définir :

```env
CHANNEL_REDIS_URL=redis://...
```

Pour améliorer les appels sur réseaux mobiles stricts, configurer un serveur TURN :

```env
TURN_SERVER_URL=turn:your-turn-domain:3478
TURN_SERVER_USERNAME=your-username
TURN_SERVER_CREDENTIAL=your-password
```

### Mobile

Les appels WebRTC utilisent des modules natifs. Il faut donc installer les dépendances et générer une build native/dev client :

```bash
npm install
npx expo prebuild
npx expo run:android
```

ou via EAS :

```bash
eas build --profile preview --platform android
```

Important : cette fonctionnalité ne doit pas être validée uniquement dans Expo Go. Elle doit être testée sur une build native Android/iOS.

## Résultat

- L’appel ne passe plus par le crédit d’appel MTN/Orange/Moov.
- L’appel se fait via Internet dans l’application.
- Le backend conserve l’historique et relaie les signaux.
- Le client et le technicien disposent d’un écran d’appel intégré.
