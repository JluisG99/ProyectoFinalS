
# Aplicación desarrollada con Streamlit para visualización de datos de biodiversidad
# Carga de bibliotecas
import streamlit as st

import pandas as pd
import geopandas as gpd
import pygeos
gpd.options.use_pygeos = True

import plotly.express as px

import folium
from folium import Marker
from folium.plugins import MarkerCluster
from folium.plugins import HeatMap
from streamlit_folium import folium_static

import math

#
# Configuración de la página
#
st.set_page_config(layout='wide')

#
#
# TÍTULO Y DESCRIPCIÓN DE LA APLICACIÓN
#

st.title('Visualización de datos de biodiversidad')
st.markdown('**Pasos para utilizar esta aplicación:**')
st.markdown('**Paso 1.** Seleccione un archivo CSV que siga el estándar [Darwin Core (DwC)](https://dwc.tdwg.org/terms/).')
st.markdown('**Paso 2.** Subir el archivo CSV basado en el DwC. El archivo debe estar separado por tabuladores. Obtenga su archivo CSV en [Infraestructura Mundial de Información en Biodiversidad (GBIF)](https://www.gbif.org/).')
st.markdown('**Paso 3.** Navegue por la app, y analice los datos arrojados')

#
# ENTRADAS
#

# Carga de datos subidos por el usuario
datos_usuarios = st.sidebar.file_uploader('Seleccione un archivo CSV que siga el estándar DwC')

# Se continúa con el procesamiento solo si hay un archivo de datos cargado
if datos_usuarios is not None:
    # Carga de registros de presencia en un dataframe con nombre de "registros"
    registros = pd.read_csv(datos_usuarios, delimiter='\t')
    # Conversión del dataframe de registros de presencia a geodataframe, identifica en código las columnas de las coordenadas
    registros = gpd.GeoDataFrame(registros, 
                                           geometry=gpd.points_from_xy(registros.decimalLongitude, 
                                                                       registros.decimalLatitude),
                                           crs='EPSG:4326')


    # Carga de polígonos de los cantones
    cantones = gpd.read_file("datos/cantones/cantones.geojson")



    # Limpieza de datos
    # Eliminación de registros con valores nulos en la columna 'species'
    registros = registros[registros['species'].notna()]
    # Cambio del tipo de datos del campo de fecha
    registros["eventDate"] = pd.to_datetime(registros["eventDate"])

    # Especificación de filtros
    # Especie
    lista_especies = registros.species.unique().tolist()
    lista_especies.sort()
    filtro_especie = st.sidebar.selectbox('Seleccione la especie', lista_especies)


    #
    # PROCESAMIENTO
    #

    # Filtrado
    registros = registros[registros['species'] == filtro_especie]

    # Cálculo de la cantidad de registros en los cantones
    # "Join" espacial de las capas de cantones y registros de presencia de especies
    cantones_con_registros = cantones.sjoin(registros, how="left", predicate="contains")
    # Conteo de registros de presencia en cada provincia
    cantones_registros = cantones_con_registros.groupby("CODNUM").agg(cantidad_presentes_registros = ("gbifID","count"))
    cantones_registros = cantones_registros.reset_index() # para convertir la serie a dataframe



    #
    # SALIDAS ------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    #

    # Tabla de registros de presencia (modifica la primer tabla que se muestra en la aplicación web)
    st.header('Registros de presencia de especies')
    st.dataframe(registros[['species', 'stateProvince', 'locality','eventDate']].rename(columns = {'species':'Especie', 'stateProvince':'Provincia', 'locality':'Localidad', 'eventDate':'Fecha'}))


    # Definición de columnas de la parte visual de nuestra aplicación, dividará el contenido en dos columnas
    col1, col2 = st.columns(2)
    col3 = st.columns(1)


    # Gráficos de cantidad de registros de presencia por provincia
    # "Join" para agregar la columna con el conteo a la capa de cantón, nos sirve para conectar pero para el gráfico usará otro atributo de provincia
    cantones_registros = cantones_registros.join(cantones.set_index('CODNUM'), on='CODNUM', rsuffix='_b')
    # Dataframe filtrado para usar en graficación
    graf_cantones_registros = cantones_registros.loc[cantones_registros['cantidad_presentes_registros'] > 0, 
                                                            ["provincia", "cantidad_presentes_registros"]].sort_values("cantidad_presentes_registros", ascending=True) #.head(20)
    graf_cantones_registros = graf_cantones_registros.set_index('provincia')  


    with col1:
        # Gráficos de historial de registros de presencia por año
        st.header('Cantidad de registros por provincia')

        fig = px.bar(graf_cantones_registros, 
                    labels={'provincia':'Provincia', 'cantidad_presentes_registros':'Registros de presencia'})    

        fig.update_layout(barmode='stack', xaxis={'categoryorder': 'total descending'})
        st.plotly_chart(fig)    
 
    
    # Gráficos de cantidad de registros de presencia por cantón
    # "Join" para agregar la columna con el conteo a la capa de cantón
    cantones_registros = cantones_registros.join(cantones.set_index('CODNUM'), on='CODNUM', rsuffix='_b')
    # Dataframe filtrado para usar en graficación
    graf_cantones_registros = cantones_registros.loc[cantones_registros['cantidad_presentes_registros'] > 0, 
                                                            ["NCANTON", "cantidad_presentes_registros"]].sort_values("cantidad_presentes_registros")
    graf_cantones_registros = graf_cantones_registros.set_index('NCANTON')  

    with col2:
        # Gráficos de historial de registros de presencia por año
        st.header('Cantidad de registros por cantón')

        fig = px.bar(graf_cantones_registros, 
                    labels={'NCANTON':'Cantón', 'cantidad_presentes_registros':'a'})    

        fig.update_layout(barmode='stack', xaxis={'categoryorder': 'total descending'})
        st.plotly_chart(fig)

    with col1:
        # Mapas de coropletas
        st.header('Mapa: Registros de presencia de especies por provincia, cantón y puntos agrupados')

        # Capa base
        m = folium.Map(
        location=[10, -84], 
        width=650, height=400, 
        zoom_start=7, 
        control_scale=True)


       # Se añaden capas base adicionales
        folium.TileLayer(
        tiles='CartoDB positron', 
        name='CartoDB positron').add_to(m)

      # ESRI NatGeo World Map
        folium.TileLayer(
        tiles='http://services.arcgisonline.com/arcgis/rest/services/NatGeo_World_Map/MapServer/MapServer/tile/{z}/{y}/{x}',
        name='NatGeo World Map',
        attr='ESRI NatGeo World Map').add_to(m)

        # Capa de coropletas
        cantones_map = folium.Choropleth(
            name="Mapa de coropletas de los registros por cantón",
            geo_data=cantones,
            data=cantones_registros,
            columns=['CODNUM', 'cantidad_presentes_registros'],
            bins=8,
            key_on='feature.properties.CODNUM',
            fill_color='Greens', 
            fill_opacity=0.5, 
            line_opacity=1,
            legend_name='Cantidad de registros de presencia por cantón',
            smooth_factor=0).add_to(m)
        
        folium.GeoJsonTooltip(['NCANTON', 'provincia']).add_to(cantones_map.geojson)


        # Capa de registros de presencia agrupados
        mc = MarkerCluster(name='Registros agrupados')
        for idx, row in registros.iterrows():
            if not math.isnan(row['decimalLongitude']) and not math.isnan(row['decimalLatitude']):
                mc.add_child(
                    Marker([row['decimalLatitude'], row['decimalLongitude'], ], 
                                    popup= "Nombre de la especie: " + str(row["species"]) + "\n" + "Provincia: " + str(row["stateProvince"]) + "\n" + "Fecha: " + str(row["eventDate"]),
                                    icon=folium.Icon(color="Blue"))).add_to(m)
        # m.add_child(mc)

        
        prov_map = folium.Choropleth(
            name="Mapa de coropletas de los registros por provincia",
            geo_data=cantones,
            data=cantones_registros,
            columns=['provincia', 'cantidad_presentes_registros'],
            bins=8,
            key_on='feature.properties.provincia',
            fill_color='Greens', 
            fill_opacity=0.5, 
            line_opacity=1,
            legend_name='Cantidad de registros de presencia por provincia',
            smooth_factor=0).add_to(m)

        folium.GeoJsonTooltip(['NCANTON', 'provincia']).add_to(prov_map.geojson)

        # Control de capas
        folium.LayerControl().add_to(m) 
        # Despliegue del mapa
        folium_static(m)
