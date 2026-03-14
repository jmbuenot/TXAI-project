# Explicación detallada de `final_report.md`

Este documento traduce y explica, en lenguaje más directo, cada sección del informe final sobre el sistema de recomendación explicable de libros.

## 1) Problema y planteamiento

### Pregunta de investigación
El proyecto quiere responder si **SHAP** puede dar explicaciones que sean:
- **Útiles (meaningful)**,
- **Estables**,
- **Fáciles de entender por personas**,
cuando un sistema recomienda libros.

### Cómo se formuló el problema
Como el dataset no tiene historial real de usuarios (qué libro leyó cada persona y cómo lo valoró), no se pudo hacer una recomendación personalizada "real" de tipo usuario-item.

Por eso, el enfoque fue:
1. Predecir la **valoración media de cada libro** a partir de variables interpretables.
2. Usar esa predicción para construir recomendaciones globales.
3. Aplicar SHAP para explicar qué variables empujan esas predicciones.

**Interpretación clave:** no se está modelando “gustos de usuarios reales”, sino “qué rasgos de un libro suelen asociarse a mejor rating”.

---

## 2) Datos, variables y modelo

### Datos
Se usa el dataset `mdhamani/goodreads-books-100k` (Kaggle), con ~100k libros.
Variables principales: `rating`, `totalratings`, `reviews`, `pages`, `genre`, `bookformat`, etc.

### Ingeniería de variables (por qué importa cada una)
- `ratings_count`: cuánta gente valoró el libro (popularidad).
- `log_ratings_count`: transformación logarítmica para controlar colas largas (evita que bestsellers extremos dominen).
- `pages`: se imputan faltantes por mediana de género principal y se limita a 2000 para controlar outliers.
- `reviews`: interacción/engagement en texto.
- Géneros multi-hot: un libro puede activar varios géneros frecuentes (top 50).
- Formato one-hot: Hardcover, Paperback, etc.

### Modelo
XGBoost de regresión con ajuste ligero de hiperparámetros.
Partición: 70% entrenamiento, 15% validación, 15% test.

### Rendimiento
- Baseline (media global): RMSE ~0.633, MAE ~0.364, R² ~0.
- XGBoost: RMSE ~0.356, MAE ~0.256, R² ~0.655.

**Lectura práctica:** mejora fuerte frente al baseline; el modelo captura buena parte del patrón de ratings.

---

## 3) Comportamiento de la recomendación

### Lista global
La correlación predicción-rating real (~0.83) es alta: los libros con score predicho alto suelen estar bien valorados.

La correlación predicción-popularidad (~0.03) es baja: el sistema no está recomendando “solo los más conocidos”.

### Diversidad
En top-20 aparecen múltiples géneros y el más frecuente ocupa solo ~20%.

**Interpretación:** hay diversidad temática razonable en recomendaciones globales.

### Perfiles sintéticos
Se crean perfiles ficticios (fantasy_fan, romance_reader, etc.) con pesos por género y preferencia de longitud.
Luego se ajusta la predicción base del modelo con:
- bonus por encaje de género,
- penalización/bonus por longitud.

**Importante:** la predicción del modelo no cambia por usuario; cambia el ranking final por reglas del perfil.

---

## 4) Explicaciones con SHAP

### 4.1 Hallazgos globales
Features más influyentes: `ratings_count`, `reviews`, `pages`, y varios géneros.

Esto indica tres señales fuertes:
1. Popularidad/interacción,
2. Contenido (género),
3. Longitud (efecto moderado).

La baja correlación con popularidad total sugiere que popularidad ayuda, pero no monopoliza la decisión.

### 4.2 Explicaciones locales
Para libros concretos:
- Títulos muy conocidos: suelen tener contribuciones positivas en ratings/reviews y género.
- Libros de nicho: pueden compensar menor popularidad con género muy favorable.
- Recomendaciones a perfiles sintéticos: SHAP explica por qué el libro tiene score alto; el perfil explica por qué aparece arriba para ese “usuario”.

### 4.3 Visualizaciones SHAP
- Beeswarm global: distribución de impactos por feature.
- Barra global: ranking de importancia media absoluta.
- Waterfall locales: descomposición de una predicción libro a libro.
- Waterfall en perfiles sintéticos: base del modelo + narrativa orientada al perfil.

---

## 5) Evaluación respecto a la pregunta de investigación

### 5.1 Alineación género-preferencia
Sin usuarios reales, la “preferencia” se interpreta como patrón agregado del conjunto.

Resultado: los géneros sí aparecen como señales clave en SHAP, por lo que hay alineación con una noción colectiva de preferencia.

### 5.2 Influencia de popularidad
Popularidad pesa mucho (ratings_count/reviews), pero no domina sola; género y otras variables también empujan.

### 5.3 Estabilidad
Se observa estabilidad cualitativa:
- Libros similares muestran perfiles SHAP parecidos.
- El top de features globales se mantiene entre muestras.

No se calcula una métrica numérica formal de estabilidad, así que esta conclusión es observacional.

### 5.4 Calidad de explicaciones
Fortalezas:
- Variables intuitivas,
- Narrativas simples y entendibles para no técnicos.

Limitaciones:
- No hay personalización real por usuario,
- `genre` puede ser incompleto/ruidoso,
- Dependencia de compatibilidad técnica de SHAP/XGBoost.

---

## 6) Conclusiones y trabajo futuro

### Respuesta final
Dentro de las limitaciones del dataset, SHAP sí da explicaciones:
- significativas,
- razonablemente estables,
- comprensibles para humanos.

### Lecciones clave
1. Se puede predecir rating medio con buen rendimiento usando variables interpretables.
2. Popularidad y género son ejes centrales.
3. Las recomendaciones no quedan secuestradas por popularidad.
4. Los perfiles sintéticos permiten adaptar narrativa explicativa, aunque no sustituyen personalización real.

### Siguientes pasos recomendados
- Incluir datos reales usuario-libro para personalización auténtica.
- Añadir señales de texto más ricas manteniendo interpretabilidad.
- Medir estabilidad SHAP con métricas cuantitativas.
- Comparar familias de modelos para estudiar trade-offs entre precisión y explicabilidad.

---

## Resumen ejecutivo (1 minuto)
Este proyecto construye un recomendador de libros basado en predecir el rating medio de cada libro y explicarlo con SHAP. El modelo funciona bien, las explicaciones son intuitivas y consistentes, y las recomendaciones resultan diversas. La principal limitación es que no hay datos de comportamiento real de usuarios, así que la personalización es simulada mediante perfiles sintéticos.
