# Estudio de voz

Estudio personal para convertir texto en audio y crear voces propias. Funciona como ElevenLabs, con un diseño propio que mezcla el vidrio líquido de APUNTY con la estructura de estudio (barra lateral, editor y ajustes).

## Qué hay ahora (paso 1)
- **Texto a voz:** editor, elección de voz, velocidad, expresividad y fidelidad, reproductor y descarga.
- **Mis voces:** biblioteca con las voces del modelo y las clonadas.
- **Clonar voz:** clon rápido subiendo una grabación de 10 a 30 segundos.
- **Diseñar voz:** pantalla preparada (llega en el paso 4).
- **Historial:** todos los audios generados.
- Modo claro y oscuro automático, con botón para cambiarlo. Se adapta a móvil.

Sin el modelo instalado, el servidor usa un **motor demo** que genera pitidos, para probar la web sin GPU.

## Arrancar en tu ordenador (Windows)
1. Instala [Python 3.11](https://www.python.org/downloads/) (marca «Add Python to PATH»).
2. Abre una terminal en esta carpeta y ejecuta:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r server/requirements.txt
   uvicorn server.main:app --reload
   ```
3. Abre http://localhost:8000

## Voz de verdad en Google Colab (gratis)
El motor real es [Chatterbox Multilingüe](https://github.com/resemble-ai/chatterbox) (licencia MIT: gratis y permite uso comercial; 23 idiomas, incluido el español). Necesita una GPU NVIDIA con más de 4 GB, así que se ejecuta en Google Colab:

1. Abre el cuaderno: [Abrir en Colab](https://colab.research.google.com/github/Jonragitt/estudio-de-voz/blob/main/colab/EstudioDeVoz.ipynb).
2. **Entorno de ejecución → Cambiar tipo de entorno de ejecución → GPU T4 → Guardar.**
3. **Entorno de ejecución → Ejecutar todo.** Acepta el permiso de Google Drive (ahí se guardan tus voces y audios, en *Mi unidad/EstudioDeVoz*).
4. Cuando termine (5–10 minutos la primera vez), pulsa el enlace **Abrir Estudio de voz**.

Los audios incluyen la marca de agua inaudible de Resemble (Perth), que viene con el modelo.

## Plan
1. ✅ Base: web y servidor.
2. ✅ Texto a voz con Chatterbox (Colab/Kaggle, con prueba en el portátil).
3. Clonar y entrenar voces con muchas grabaciones o enlaces de vídeo.
4. Diseñar voces desde cero.

Usa solo tu voz, voces con permiso o voces diseñadas, sobre todo si vas a usarlas en algo de pago.
