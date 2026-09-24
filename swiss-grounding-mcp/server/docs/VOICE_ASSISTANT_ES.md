# Asistente de Voz — Swiss Grounding MCP

Documento técnico para el equipo: cómo funciona el asistente de voz manos
libres construido sobre las herramientas MCP de transporte público suizo.

**Archivo principal:** `voice_assistant.py` (raíz de `server/`)

---

## 1. Arquitectura general

El asistente es un bucle conversacional que conecta cinco etapas:

```
MICRÓFONO ──> STT (ElevenLabs Scribe) ──> INTENT ROUTER ──> TOOLS (OJP 2.0 / AeroDataBox)
    ^                                                            │
    └──── SPEAKER <── TTS (ElevenLabs) <── RENDERER (_say) <─────┘
```

| Componente | Rol | Implementación |
|---|---|---|
| `MicRecorder` | Captura de audio con VAD por energía | `sounddevice` InputStream, 16 kHz mono |
| `ElevenLabsSpeech.transcribe` | Voz → texto | Scribe `scribe_v1`, detección automática de idioma |
| `route_intent` | Texto → herramienta + argumentos | Patrones regex EN/DE/FR |
| `ToolBox` | Fachada de las 7 herramientas MCP | Llama **in-process** a las mismas funciones que `server.py` registra vía MCP |
| `_say` | Resultado estructurado → respuesta hablada | Renderers por tipo de modelo Pydantic |
| `ElevenLabsSpeech.synthesize` | Texto → audio | `eleven_multilingual_v2`, formato `pcm_24000` |
| `Speaker` | Reproducción | `sounddevice.play` (PCM s16 → float32) |

Punto clave de diseño: **no hay servidor MCP de por medio**. `ToolBox` invoca
directamente las mismas funciones (`find_train_connections`,
`get_station_board`, `find_station_disruptions`, `find_flight_by_number`,
`search_airport_flights`, `get_airport_guidance`, `connect_flight_to_train`)
que el MCP expone a clientes externos — una sola implementación, dos
interfaces (voz y protocolo MCP).

## 2. Flujo de datos: de frase hablada a consulta OJP

`route_intent(text, tools)` aplica reglas en orden de prioridad:

1. **Palabras de aviación** (`flight`, `flug`, `vol`, `airport`, `flughafen`):
   - "flight LX14 ... train to Bern" → `connect_flight_to_train` (número de vuelo
     por regex `[A-Z]{2}\d{1,4}`, buffer de transbordo 45 min)
   - "status of flight LX14" → `find_flight_by_number` (fecha = hoy, dirección
     por palabras clave arrival/departure)
   - "airport transfers / baggage / customs" → `get_airport_guidance` (mapa de
     temas → topics oficiales de flughafen-zuerich.ch)
   - "flights to/from JFK" → `search_airport_flights` (código IATA de 3 letras)
2. **Disrupciones** (`disruption`, `delayed`, `cancelled`, `störung`,
   `verspätung`, `perturbation`) → `find_disruptions` con la estación extraída.
3. **Paneles de estación** (`departures`, `arrivals`, `abfahrt`, `ankunft`,
   `board`) → `get_station_board` con modo y estación.
4. **Conexiones** (`from X to Y`, `X nach Y`, `de X a Y`) → `find_connections`.
5. **Utterance corta sin keywords** (≤4 palabras, ej. respuesta de
   clarificación "bern hauptbahnhof") → `get_station_board` (departures).
6. **Sin coincidencia** → mensaje honesto de clarificación.

Limpieza de entrada (`_clean_name` + `_TIME_TAIL`): elimina puntuación final
y calificadores temporales ("next 2 hours", "in 30 minutes", "heute",
"demain") que de otro modo contaminan el nombre de estación — bug real
detectado durante la evaluación Galtea.

Las herramientas en sí son las ya verificadas del servidor: resolución de
estación vía `OJPLocationInformationRequest` (con normalización de acentos y
desambiguación por probabilidad), control de alcance suizo (`ch:` SLOID /
`85xxxxx` UIC — cross-border permitido si un extremo es suizo), consulta
`OJPTripRequest` / `OJPStopEventRequest`, truncado de resultados y
provenance (`opentransportdata.swiss OJP 2.0` + timestamp UTC).

## 3. Pipeline de voz

- **Captura:** `sounddevice.InputStream` a 16 kHz mono, bloques de 50 ms.
  VAD por energía RMS: la grabación "empieza" cuando el nivel supera
  `SPEECH_RMS = 0.012` y termina tras `SILENCE_S = 1.3 s` de silencio
  (máx. 20 s; abandono tras 15 s si nunca hubo voz). Resultado: WAV PCM16
  en memoria vía `soundfile`.
- **STT:** el WAV se envía a `speech_to_text.convert(model_id="scribe_v1")`.
  Scribe detecta el idioma automáticamente → soporta EN/DE/FR sin
  configuración.
- **TTS:** `text_to_speech.convert` con `output_format="pcm_24000"` — PCM
  crudo que se reproduce sin decodificador: `np.frombuffer(int16)` →
  `sd.play` (bloqueante hasta terminar). Voz por defecto "Rachel",
  sobreescribible con `ELEVENLABS_VOICE_ID`.
- **Clave API:** se lee `ELEVENLABS_API_KEY` (o `ELEVEN_LABS_API_KEY`) de
  `.env`/`.env.local`; el loader tolera espacios y una clave pegada dos
  veces (la detecta y la desduplica).

## 4. Robustez y bucle multi-turno

```python
while True:
    transcript = listen()          # mic → STT
    if is_goodbye(transcript):     # adiós → despedida + break
        break
    say(answer(transcript))        # router → tool → render → TTS → play
    # ... y vuelve a escuchar automáticamente
```

- **Reanudación automática:** tras hablar la respuesta, el bucle vuelve a
  `listen()` sin intervención — conversación de ida y vuelta real.
- **Silencio:** si nadie habla en 15 s, el recorder devuelve el audio y la
  transcripción vacía simplemente reinicia la escucha (sin crash, sin
  pregunta fantasma).
- **Terminación:** `goodbye`, `bye`, `tschüss`, `tschau`, `au revoir`,
  `arrivederci`, `ciao`, `stop listening`, `exit`, `quit` — además de
  Ctrl+C con salida limpia.
- **Aislamiento de errores:** cada turno va en try/except — un fallo de API,
  de dispositivo o de parsing imprime `[error] ...` y el bucle continúa.
  Los errores de las tools nunca lanzan excepción: devuelven
  `status="source_error"`/`"not_found"`/`"needs_clarification"` que `_say`
  convierte en una respuesta hablada honesta ("Did you mean: ...?").

## 5. Conexión con la evaluación Galtea

`galtea_eval.py` reutiliza **exactamente el mismo router y ToolBox** —
el agente evaluado es el mismo cerebro que el asistente de voz:

```python
def agent(user_message: str) -> str:
    name, result = route_intent(user_message, _tools)
    if name == "clarify":
        return json.dumps({"status": "needs_clarification", "message": result})
    return result.model_dump_json()   # schema canónico MCP: status + datos + provenance
```

Hallazgos que Galtea reveló y que mejoraron el asistente:

1. **PEP 563 rompía la detección de firma** del SDK (`str` anotado llegaba
   como string `'str'` → el SDK pasaba `list[dict]` → todos los traces
   FAILED/SKIPPED). Corregido quitando `from __future__ import annotations`.
2. **El juez exige el schema estructurado** — por eso el agente devuelve
   `model_dump_json()` con `status`, `connections`/`events`/`candidates` y
   `provenance` literal en vez de prosa.
3. **Bugs reales de routing descubiertos por el eval:** calificadores
   temporales contaminando nombres de estación ("bern next 2 hours" →
   Riggisberg) y utterances cortas de clarificación sin salida — ambos
   corregidos en `voice_assistant.py` y cubiertos por tests.

Resultados: run final `run_l61rzl2iqac2vah5fn8fyk5t` → **51/51 evaluaciones
SUCCESS, 0 SKIPPED**, media 0.43 (mejorando desde 0.235 en dos iteraciones).
Plataforma: platform.galtea.ai.

## Verificación realizada

- `--self-test`: 6/6 PASS con hardware y APIs reales — captura de mic (128 KB),
  round-trip STT exacto sobre audio sintetizado, llamadas OJP en vivo
  (conexiones Bern→Zürich HB reales), TTS (800 KB PCM), reproducción por
  altavoz, detección de despedida.
- Bucle real 45 s sin intervención: saludo → escucha → timeout de silencio →
  re-escucha, sin crashes.
- Suite completa: **168 tests unitarios, 0 fallos** (más 6 escenarios de
  compliance en vivo, gated por `SWISSCOM_LIVE_EVAL=1`).

## Comandos

```bash
cd swiss-grounding-mcp/server
./.venv/Scripts/python voice_assistant.py              # bucle de voz completo
./.venv/Scripts/python voice_assistant.py --self-test  # verificación E2E sin micrófono humano
./.venv/Scripts/python voice_assistant.py --text       # escribir en vez de hablar
./.venv/Scripts/python voice_assistant.py --mute       # sin TTS (solo texto)
./.venv/Scripts/python voice_assistant.py --list-devices
./.venv/Scripts/python galtea_eval.py                  # evaluación Galtea
```

Ejemplos de frases: "next train from Bern to Zurich HB", "departures from
Basel SBB", "Bern nach Zürich", "any disruptions at Bern?", "status of
flight LX14", "how do airport transfers work?", "goodbye" para terminar.

Único ajuste posible en la demo: `SPEECH_RMS` (0.012) — bajarlo si el mic
es silencioso, subirlo si la sala es ruidosa.
