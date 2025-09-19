import streamlit as st
import requests
import json
import datetime
import time
import pandas as pd

# Las coordenadas por defecto  son de Madrid
lat = 40.4165
lon = -3.70256

# Obtener coordenadas de una ciudad
def coordenadas_ciudad(ciudad):
    url = f"https://nominatim.openstreetmap.org/search?city={ciudad}&format=json&limit=1"
    resp = requests.get(url, headers={"User-Agent": "app-riego"})
    datos = resp.json()
    return float(datos[0]["lat"]), float(datos[0]["lon"]) if datos!= None else None

def pillar_valor(arr, i, default=None):
    try:
        return arr[i]
    except (IndexError, TypeError):
        return default
def llamada_api(lat, lon):
    url = f"https://my.meteoblue.com/packages/basic-1h_agro-1h_agromodelleafwetness-1h_agromodelspray-1h_soiltrafficability-1h?apikey=5t0XUA7hEy3PmpTC&lat={lat}&lon={lon}&asl=665&format=json"
    resp = requests.get(url)
    datos = resp.json()
    clima_horas = datos.get("data_1h", {})
    clima_dia = datos.get("data_day", {})
    suelo_datos = datos.get("soiltrafficability_1h", {})
    agro_datos = datos.get("agro_1h", {})

    # Hora actual
    ahora = datetime.datetime.now()
    hora_actual = ahora.strftime("%Y-%m-%d %H:00")

    tiempos = clima_horas.get("time", [])
    try:
        i = tiempos.index(hora_actual)
    except ValueError:
        i = 0

    temperatura = pillar_valor(clima_horas.get("temperature", []), i)
    humedad_rel = pillar_valor(clima_horas.get("relativehumidity", []), i)
    presion = pillar_valor(clima_horas.get("pressure", []), i)
    viento = pillar_valor(clima_horas.get("windspeed", []), i)
    momento = tiempos[i] if tiempos and len(tiempos) > i else None
    prob_precip = pillar_valor(clima_horas.get("precipitation_probability", []), i)
    temp_suelo = pillar_valor(clima_horas.get("soiltemperature_0to10cm", []), i)
    humedad_suelo = pillar_valor(clima_horas.get("soilmoisture_0to10cm", []), i)
    arena = pillar_valor(suelo_datos.get("sand", []), i)
    limo = pillar_valor(suelo_datos.get("silt", []), i)
    arcilla = pillar_valor(suelo_datos.get("clay", []), i)
    evapotranspiracion = pillar_valor(clima_horas.get("potentialevapotranspiration", []), i)
    ventana_pulv = pillar_valor(clima_horas.get("spraywindow", []), i)
    st.write(f"Datos para: {momento}")
    return(temperatura, humedad_rel, presion, viento, prob_precip, temp_suelo, humedad_suelo, arena, limo, arcilla, evapotranspiracion, ventana_pulv)

# Recomendaciones de riego
def recomendacion_riego(datos_actuales, cultivo):
    recomendaciones = []
    recomendado = 7 // cultivo.get("frecuencia_riego_dias", 1)
    veces = datos_actuales.get("veces_regado")
    humedad = datos_actuales["humedad_suelo"]
    humedad_obj = cultivo["humedad_suelo"]

    # Riego según humedad y frecuencia
    if veces >= recomendado:
        if humedad < humedad_obj - 10:
            recomendaciones.append(("warning", "Ya regaste lo suficiente, pero la humedad está baja."))
        else:
            recomendaciones.append(("success", f"Llevas {veces} riegos esta semana. No hace falta más."))
    elif veces < recomendado:
        if humedad < humedad_obj:
            recomendaciones.append(("warning", f"Llevas {veces} riegos esta semana y la humedad está baja. Conviene regar hoy."))
        elif humedad > humedad_obj + 10:
            recomendaciones.append(("success", "El suelo está bien de humedad, no hace falta regar."))
        else:
            recomendaciones.append(("info", "La humedad es correcta, puedes hacer un riego ligero si lo prefieres."))
    else:
        recomendaciones.append(("info", "Riego semanal dentro de lo esperado."))

    # Temperatura del suelo
    if datos_actuales["temperatura_suelo"] < cultivo["temperatura_suelo"] - 2:
        recomendaciones.append(("info", "La temperatura del suelo está algo baja."))
    elif datos_actuales["temperatura_suelo"] > cultivo["temperatura_suelo"] + 2:
        recomendaciones.append(("warning", "Temperatura del suelo algo alta, vigila el riego."))

    # Transitabilidad del suelo, asumo que la planta está en su suelo adecuado
    tipo = cultivo["tipo_suelo"]
    trans = None
    if tipo == "sand":
        trans = arena
    elif tipo == "silt":
        trans = limo
    elif tipo == "clay":
        trans = arcilla

    if trans is not None:
        if trans < 0.3:
            recomendaciones.append(("warning", f"El suelo ({tipo}) está poco transitable, evita maquinaria pesada."))
        elif trans > 0.7:
            recomendaciones.append(("success", f"El suelo ({tipo}) está muy transitable, puedes usar maquinaria."))
        else:
            recomendaciones.append(("info", f"El suelo ({tipo}) tiene transitabilidad media."))
    else:
        recomendaciones.append(("info", f"No se pudo calcular la transitabilidad del suelo ({tipo})."))

    # Ventana de pulverización
    if ventana_pulv is not None:
        if ventana_pulv > 2:
            recomendaciones.append(("success", "Buena ventana para aplicar tratamientos foliares."))
        else:
            recomendaciones.append(("info", "La ventana de pulverización es limitada, espera si puedes."))

    # Fumigación
    mes_actual = datetime.datetime.now().strftime('%B').lower()
    if mes_actual in [m.lower() for m in cultivo["meses_fumigar"]]:
        recomendaciones.append(("info", "Este mes conviene fumigar para prevenir plagas."))

    return recomendaciones

# Cargar archivo JSON con los cultivos
with open("Plantas.json", "r") as f:
    plantas_data = json.load(f)

cultivos = plantas_data.get("cultivos", [])

# Interfaz Streamlit

st.title("Asistente de Riego")

ciudad=st.text_input("Introduce tu ciudad:", key="ciudad")
veces_regado = st.number_input("¿Cuántas veces has regado esta semana?", min_value=0, max_value=7, step=1, key="veces_regado")

st.selectbox("Selecciona tu cultivo:", [c["nombre"] for c in cultivos], key="cultivo")

if ciudad != None:
    lat,lon=coordenadas_ciudad(ciudad)
# Llamada a la API de meteoblue


temperatura, humedad_rel, presion, viento, prob_precip, temp_suelo, humedad_suelo, arena, limo, arcilla, evapotranspiracion, ventana_pulv=llamada_api(lat, lon)
# Botón para mostrar instrucciones

if st.button("Instrucciones de riego"):
    cultivo_sel = next((c for c in cultivos if c["nombre"] == st.session_state["cultivo"]), None)
    datos_actuales = {
        "humedad_suelo": humedad_suelo if humedad_suelo is not None else 30,
        "temperatura_suelo": temp_suelo if temp_suelo is not None else 15,
        "tipo_suelo": cultivo_sel["tipo_suelo"] if cultivo_sel else "silt",
        "veces_regado": veces_regado
    }

    if cultivo_sel:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Humedad actual", f"{datos_actuales['humedad_suelo']} %")
            st.metric("Humedad ideal", f"{cultivo_sel['humedad_suelo']} %")
        with col2:
            st.metric("Temp. suelo actual", f"{datos_actuales['temperatura_suelo']} °C")
            st.metric("Temp. suelo ideal", f"{cultivo_sel['temperatura_suelo']} °C")

        # Gráficos de comparación
        df_humedad = pd.DataFrame({"Humedad": [datos_actuales["humedad_suelo"], cultivo_sel["humedad_suelo"]]}, index=["Actual", "Ideal"])
        st.write("Comparativa de humedad del suelo")
        st.bar_chart(df_humedad)

        df_temp = pd.DataFrame({"Temperatura": [datos_actuales["temperatura_suelo"], cultivo_sel["temperatura_suelo"]]}, index=["Actual", "Ideal"])
        st.write("Comparativa de temperatura del suelo")
        st.bar_chart(df_temp)

        # Recomendaciones
        resultado = recomendacion_riego(datos_actuales, cultivo_sel)
        st.subheader("Recomendaciones de riego")
        for tipo, mensaje in resultado:
            if tipo == "success":
                st.success(mensaje)
            elif tipo == "warning":
                st.warning(mensaje)
            elif tipo == "info":
                st.info(mensaje)
            else:
                st.write(mensaje)
    else:
        st.error("Selecciona un cultivo válido")
