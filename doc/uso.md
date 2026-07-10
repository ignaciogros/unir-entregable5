# Guía de uso

La aplicación tiene dos pantallas: **Administración**, donde se gestionan los documentos, y **Chat**,
donde se pregunta sobre ellos. Se navega entre ambas desde el menú superior.

---

## 1. Iniciar sesión

Abre la aplicación e introduce el usuario y la contraseña definidos en `APP_USER` y `APP_PASSWORD`.

La sesión dura 8 horas. Si intentas entrar en cualquier página sin haber iniciado sesión, se te
redirige aquí automáticamente.

---

## 2. Subir documentos

En **Administración**, usa el formulario de subida para añadir un PDF.

Restricciones:

- Extensión `.pdf` y contenido realmente PDF (se comprueba la cabecera del fichero).
- Tamaño máximo **20 MB**.
- El PDF debe tener **texto seleccionable**. Los documentos escaneados como imagen no se pueden
  indexar, porque la aplicación no aplica OCR.

Si subes un fichero con un nombre que ya existe, se sustituye y vuelve a marcarse como pendiente de
procesar.

La tabla muestra cada documento con su tamaño, fecha de subida y estado: **pendiente** o
**procesado**.

---

## 3. Procesar

Subir un PDF no basta para poder preguntar sobre él. Hay que pulsar **Procesar**, que lanza la
ingesta de **todos** los documentos de la tabla:

1. Cada PDF se lee página a página.
2. El texto se trocea en fragmentos solapados.
3. Cada fragmento se convierte en un vector con Azure OpenAI.
4. Los vectores se guardan en una colección nueva, que pasa a ser la activa.

El proceso corre en segundo plano y la página muestra el progreso, actualizándose sola. Cuando
termina, todos los documentos aparecen como **procesado** y el chat ya puede consultarlos.

Un PDF de pocas decenas de páginas tarda del orden de un minuto. La duración depende sobre todo del
número de fragmentos, ya que cada uno requiere una llamada a Azure OpenAI.

> **Importante:** «Procesar» reindexa todos los documentos, no solo los nuevos. Es la operación
> correcta después de añadir o borrar cualquier PDF.

---

## 4. Restaurar la versión anterior

Cada vez que procesas, la colección de vectores anterior se conserva como copia de seguridad. Si el
resultado no es el esperado —por ejemplo, borraste un PDF por error y reprocesaste—, el botón
**Restaurar versión anterior** devuelve el índice al estado previo de forma inmediata.

El botón solo aparece cuando existe una versión anterior. Se guardan como mucho **dos** versiones: al
procesar por tercera vez, la más antigua se elimina.

Restaurar no toca los ficheros PDF, solo el índice de vectores que consulta el chat.

---

## 5. Eliminar documentos

El botón de borrado de cada fila elimina el fichero del disco **y** sus vectores de la colección
activa, de modo que el chat deja de citarlo al instante. No hace falta reprocesar para que
desaparezca de las respuestas.

---

## 6. Conversar

En **Chat**, escribe una pregunta en lenguaje natural y envíala. La respuesta aparece sin recargar la
página.

Debajo de cada respuesta se listan las **fuentes** que la sustentan:

```
Fuentes
  📄 tema1.pdf                    pág. 12
     Fiabilidad ▓▓▓▓▓▓▓▓▓░  92%
  📄 tema1.pdf                    pág. 14
     Fiabilidad ▓▓▓▓▓▓▓▓░░  87%
  📄 tema3.pdf                    pág.  3
     Fiabilidad ▓▓▓▓▓▓▓▓░░  81%
```

- El **nombre del fichero** es un enlace: al pulsarlo se abre el PDF original.
- La **página** indica dónde está el fragmento citado.
- **Fiabilidad** es la similitud entre tu pregunta y el fragmento recuperado, expresada como
  porcentaje y como barra. La barra cambia de color según el tramo (alto ≥ 75 %, medio ≥ 50 %, bajo
  por debajo). No mide si la respuesta es correcta, sino cuán relacionado está el fragmento con lo
  que preguntaste.

### Qué esperar de las respuestas

El asistente **solo** usa el contenido de tus documentos. Si preguntas algo que no está en ellos,
responderá exactamente:

> No encuentro información sobre eso en los documentos disponibles.

Esto es intencionado. Un modelo de lenguaje sabe responder «¿cuál es la capital de Francia?», pero
aquí se le prohíbe hacerlo: la utilidad de la herramienta está en que todo lo que afirma se puede
rastrear hasta una página concreta de un PDF concreto.

Cuando ningún fragmento recuperado se parece lo bastante a la pregunta, aparece el aviso
**⚠️ Baja confianza**. Significa que la respuesta se apoya en material poco relacionado y conviene
comprobar las fuentes antes de fiarse.

### Preguntas encadenadas

El chat recuerda los **6 últimos intercambios**, así que puedes preguntar «¿y cómo se relaciona eso
con X?» sin repetir el contexto. El historial se guarda en una cookie firmada y caduca a las 8 horas.

---

## Accesibilidad

Toda la interfaz es navegable **solo con teclado**: `Tab` recorre los controles, `Enter` envía los
formularios, y el elemento activo siempre tiene el foco visible. Los textos cumplen el contraste
WCAG AA, las tablas y formularios tienen etiquetas asociadas, y las respuestas del chat se anuncian a
los lectores de pantalla mediante regiones `aria-live`.
