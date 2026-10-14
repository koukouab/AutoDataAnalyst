
import streamlit as st
import pandas as pd
import plotly.express as px
from io import StringIO, BytesIO
import hashlib

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="AutoData Analyst",
    page_icon="📊",
    layout="wide"
)

st.title("📊 AutoData Analyst")
st.write(
    "Explorez votre DataFrame, identifiez les problèmes "
    "de qualité et préparez vos données pour l'analyse."
)

# --------------------------------------------------
# IMPORT DES DONNÉES : FICHIER CSV OU LIEN URL
# --------------------------------------------------

import hashlib
from io import BytesIO

st.subheader("Importer les données")

mode_import = st.radio(
    "Comment souhaitez-vous importer vos données ?",
    ["Fichier CSV depuis mon ordinateur", "Lien direct vers un CSV"],
    horizontal=True,
    key="mode_import"
)

df_charge = None
signature_fichier = None

if mode_import == "Fichier CSV depuis mon ordinateur":

    fichier = st.file_uploader(
        "Sélectionnez votre fichier CSV",
        type=["csv"],
        key="import_csv"
    )

    if fichier is None:
        st.info("Importez un fichier CSV pour commencer.")
        st.stop()

    contenu_csv = fichier.getvalue()
    signature_fichier = hashlib.md5(contenu_csv).hexdigest()

    try:
        df_charge = pd.read_csv(
            BytesIO(contenu_csv),
            sep=None,
            engine="python"
        )
    except Exception as erreur:
        st.error(f"Impossible de lire le fichier CSV : {erreur}")
        st.stop()

else:

    url_csv = st.text_input(
        "Collez le lien direct vers votre fichier CSV",
        placeholder="https://exemple.com/donnees.csv",
        key="url_csv"
    )

    if not url_csv.strip():
        st.info("Collez un lien direct vers un fichier CSV pour commencer.")
        st.stop()

    if not url_csv.strip().lower().startswith(("https://", "http://")):
        st.error("Le lien doit commencer par http:// ou https://.")
        st.stop()

    if st.button("Charger les données depuis le lien", key="charger_url"):
        try:
            import requests

            reponse = requests.get(
                url_csv.strip(),
                timeout=20
            )
            reponse.raise_for_status()

            contenu_csv = reponse.content
            signature_fichier = hashlib.md5(contenu_csv).hexdigest()

            df_charge = pd.read_csv(
                BytesIO(contenu_csv),
                sep=None,
                engine="python"
            )

            st.session_state["url_chargee"] = url_csv.strip()
            st.session_state["contenu_url"] = contenu_csv
            st.session_state["signature_url"] = signature_fichier

        except Exception as erreur:
            st.error(f"Impossible de charger le CSV depuis ce lien : {erreur}")
            st.stop()

    # Conserver le résultat du chargement lors des reruns Streamlit
    if st.session_state.get("url_chargee") == url_csv.strip():
        contenu_csv = st.session_state["contenu_url"]
        signature_fichier = st.session_state["signature_url"]

        try:
            df_charge = pd.read_csv(
                BytesIO(contenu_csv),
                sep=None,
                engine="python"
            )
        except Exception as erreur:
            st.error(f"Impossible de lire le CSV : {erreur}")
            st.stop()

    else:
        st.stop()

# Vérifier que les données ont bien été chargées
if df_charge is None or len(df_charge.columns) == 0:
    st.error("Aucune colonne n'a été détectée dans les données.")
    st.stop()

# Initialiser les données uniquement lors d'un nouvel import
if st.session_state.get("signature_fichier") != signature_fichier:
    st.session_state["df_original"] = df_charge.copy(deep=True)
    st.session_state["df_nettoye"] = df_charge.copy(deep=True)
    st.session_state["signature_fichier"] = signature_fichier
    st.session_state["doublons_verifies"] = False
    st.session_state["nb_doublons_verifies"] = 0
    st.session_state["criteres_verifies"] = []
    st.session_state["demande_reinitialisation"] = False

# Les analyses utilisent la copie de travail actuelle
df = st.session_state["df_nettoye"]

# --------------------------------------------------
# BOUTON DE REINITIALISATION
# --------------------------------------------------

st.subheader("Gestion des données")

col_actualisation, col_reinitialisation = st.columns(2)

with col_actualisation:
    if st.button(
        "🔄 Actualiser les analyses",
        use_container_width=True,
        key="actualiser_analyses"
    ):
        st.rerun()

with col_reinitialisation:
    if st.button(
        "↩️ Réinitialiser les données",
        use_container_width=True,
        key="demander_reinitialisation"
    ):
        st.session_state["demande_reinitialisation"] = True

# Demander confirmation avant de perdre les nettoyages
if st.session_state.get("demande_reinitialisation", False):

    st.warning(
        "Cette action annulera les nettoyages effectués "
        "et restaurera les données du CSV original."
    )

    col_confirmer, col_annuler = st.columns(2)

    with col_confirmer:
        if st.button(
            "Confirmer la réinitialisation",
            type="primary",
            use_container_width=True,
            key="confirmer_reinitialisation"
        ):
            st.session_state["df_nettoye"] = (
                st.session_state["df_original"].copy(deep=True)
            )

            st.session_state["doublons_verifies"] = False
            st.session_state["nb_doublons_verifies"] = 0
            st.session_state["criteres_verifies"] = []
            st.session_state["demande_reinitialisation"] = False

            st.rerun()

    with col_annuler:
        if st.button(
            "Annuler",
            use_container_width=True,
            key="annuler_reinitialisation"
        ):
            st.session_state["demande_reinitialisation"] = False
            st.rerun()

# --------------------------------------------------
# CLASSIFICATION DES COLONNES
# --------------------------------------------------

colonnes_numeriques = df.select_dtypes(
    include="number"
).columns.tolist()

colonnes_dates = df.select_dtypes(
    include=["datetime", "datetimetz"]
).columns.tolist()

colonnes_textuelles = [
    col for col in df.columns
    if col not in colonnes_numeriques
    and col not in colonnes_dates
]

# --------------------------------------------------
# 1. VUE D'ENSEMBLE
# --------------------------------------------------

st.header("1. Vue d'ensemble")

nb_lignes, nb_colonnes = df.shape
nb_doublons = int(df.duplicated().sum())
nb_manquants = int(df.isna().sum().sum())

col1, col2, col3, col4 = st.columns(4)

col1.metric("Lignes", nb_lignes)
col2.metric("Colonnes", nb_colonnes)
col3.metric("Lignes en doublon", nb_doublons)
col4.metric("Cellules manquantes", nb_manquants)

st.caption(
    f"Dimensions : {nb_lignes} lignes × {nb_colonnes} colonnes"
)

st.caption(
    "Les indicateurs ci-dessus portent sur les données de travail "
    "actuelles, après les nettoyages déjà appliqués."
)

# --------------------------------------------------
# 2. EXPLORATION DU DATAFRAME
# --------------------------------------------------

# --------------------------------------------------
# 2. EXPLORATION DU DATAFRAME
# --------------------------------------------------

st.header("2. Exploration du DataFrame")

onglets = st.tabs([
    "Aperçu complet",
    "Head",
    "Tail",
    "Shape et colonnes",
    "Info"
])

with onglets[0]:
    st.subheader("Aperçu des données")
    st.dataframe(df, use_container_width=True, height=450)

with onglets[1]:
    nombre_head = st.number_input(
        "Nombre de premières lignes",
        min_value=1,
        max_value=max(1, len(df)),
        value=min(5, max(1, len(df))),
        key="nombre_head"
    )
    st.dataframe(df.head(int(nombre_head)), use_container_width=True)

with onglets[2]:
    nombre_tail = st.number_input(
        "Nombre de dernières lignes",
        min_value=1,
        max_value=max(1, len(df)),
        value=min(5, max(1, len(df))),
        key="nombre_tail"
    )
    st.dataframe(df.tail(int(nombre_tail)), use_container_width=True)

with onglets[3]:
    st.subheader("Shape")
    st.write(f"Nombre de lignes : **{df.shape[0]}**")
    st.write(f"Nombre de colonnes : **{df.shape[1]}**")

    st.subheader("Columns")
    st.dataframe(
        pd.DataFrame({"Nom des colonnes": df.columns.tolist()}),
        use_container_width=True
    )

with onglets[4]:
    st.subheader("Info")
    tampon = StringIO()
    df.info(buf=tampon, memory_usage="deep")
    st.code(tampon.getvalue(), language="text")

# --------------------------------------------------
# 3. CLASSIFICATION DES COLONNES
# --------------------------------------------------

st.header("3. Classification des colonnes")

st.write(
    "Classification fondée sur les types reconnus par Pandas. "
    "Les dates stockées en texte ne sont pas encore reconnues "
    "automatiquement comme des dates."
)

tab_num, tab_texte, tab_dates = st.tabs([
    f"Numériques ({len(colonnes_numeriques)})",
    f"Non numériques ({len(colonnes_textuelles)})",
    f"Dates ({len(colonnes_dates)})"
])

with tab_num:
    if colonnes_numeriques:
        st.dataframe(
            pd.DataFrame({
                "Colonne": colonnes_numeriques,
                "Type": [str(df[col].dtype) for col in colonnes_numeriques]
            }),
            use_container_width=True
        )
    else:
        st.info("Aucune colonne numérique détectée.")

with tab_texte:
    if colonnes_textuelles:
        st.dataframe(
            pd.DataFrame({
                "Colonne": colonnes_textuelles,
                "Type": [str(df[col].dtype) for col in colonnes_textuelles]
            }),
            use_container_width=True
        )
    else:
        st.info("Aucune colonne non numérique détectée.")

with tab_dates:
    if colonnes_dates:
        st.dataframe(
            pd.DataFrame({
                "Colonne": colonnes_dates,
                "Type": [str(df[col].dtype) for col in colonnes_dates]
            }),
            use_container_width=True
        )
    else:
        st.info("Aucune colonne de type date détectée.")

# --------------------------------------------------
# 4. STATISTIQUES DESCRIPTIVES
# --------------------------------------------------

st.header("4. Statistiques descriptives")

st.subheader("4.1 Colonnes numériques")

if colonnes_numeriques:
    statistiques_num = df[colonnes_numeriques].describe().T
    statistiques_num["Médiane"] = df[colonnes_numeriques].median()
    statistiques_num["Valeurs manquantes"] = (
        df[colonnes_numeriques].isna().sum()
    )
    statistiques_num["Valeurs distinctes"] = (
        df[colonnes_numeriques].nunique()
    )

    st.dataframe(
        statistiques_num.round(3),
        use_container_width=True
    )
else:
    st.info("Aucune colonne numérique à analyser.")

st.subheader("4.2 Colonnes non numériques")

if colonnes_textuelles:
    statistiques_texte = []

    for col in colonnes_textuelles:
        serie = df[col]
        frequences = serie.value_counts(dropna=True)

        statistiques_texte.append({
            "Colonne": col,
            "Valeurs renseignées": int(serie.notna().sum()),
            "Valeurs manquantes": int(serie.isna().sum()),
            "Valeurs distinctes": int(serie.nunique()),
            "Valeur la plus fréquente": (
                str(frequences.index[0])
                if not frequences.empty else None
            ),
            "Fréquence maximale": (
                int(frequences.iloc[0])
                if not frequences.empty else 0
            )
        })

    st.dataframe(
        pd.DataFrame(statistiques_texte),
        use_container_width=True
    )
else:
    st.info("Aucune colonne non numérique à analyser.")

st.subheader("4.3 Colonnes de dates")

if colonnes_dates:
    for col in colonnes_dates:
        serie = df[col]
        st.write(f"**{col}**")
        st.write(
            f"Première date : {serie.min()} | "
            f"Dernière date : {serie.max()} | "
            f"Valeurs manquantes : {serie.isna().sum()}"
        )
else:
    st.info("Aucune colonne de date détectée.")

# --------------------------------------------------
# 5. VALEURS MANQUANTES
# --------------------------------------------------

st.header("5. Analyse des valeurs manquantes")

manquants = df.isna().sum()
pourcentages = (manquants / max(1, len(df)) * 100).round(2)

analyse_manquants = pd.DataFrame({
    "Colonne": df.columns,
    "Valeurs manquantes": manquants.values,
    "Pourcentage manquant (%)": pourcentages.values,
    "Valeurs renseignées": df.notna().sum().values
})

analyse_manquants = analyse_manquants.sort_values(
    "Pourcentage manquant (%)",
    ascending=False
)

st.dataframe(analyse_manquants, use_container_width=True)

if (manquants > 0).any():
    st.warning(
        f"{int((manquants > 0).sum())} colonne(s) contiennent "
        "des valeurs manquantes."
    )
else:
    st.success("Aucune valeur manquante détectée.")

# --------------------------------------------------
# 6. DOUBLONS
# --------------------------------------------------

st.header("6. Analyse des doublons")

doublons = df.loc[df.duplicated(keep=False)]

if not doublons.empty:
    st.warning(
        f"{int(df.duplicated().sum())} ligne(s) en doublon "
        "après la première occurrence."
    )

    if st.checkbox("Afficher les lignes appartenant à des doublons"):
        st.dataframe(doublons, use_container_width=True)
else:
    st.success("Aucun doublon détecté.")

# --------------------------------------------------

# --------------------------------------------------
# 7. EXPLORATION DES VALEURS ET FREQUENCES
# --------------------------------------------------

st.header("7. Exploration des valeurs et fréquences")

colonne_unique = st.selectbox(
    "Choisissez une colonne à analyser",
    options=df.columns.tolist(),
    key="colonne_frequences"
)

serie_unique = df[colonne_unique]

nb_distinctes = int(serie_unique.nunique(dropna=True))
nb_manquantes = int(serie_unique.isna().sum())
nb_renseignees = int(serie_unique.notna().sum())

col1, col2, col3 = st.columns(3)

col1.metric("Valeurs distinctes", nb_distinctes)
col2.metric("Valeurs manquantes", nb_manquantes)
col3.metric("Valeurs renseignées", nb_renseignees)

st.subheader("Fréquence de chaque valeur")

if nb_renseignees > 0:

    frequences = serie_unique.value_counts(
        dropna=True
    ).rename_axis("Valeur").reset_index(name="Effectif")

    frequences["Pourcentage (%)"] = (
        frequences["Effectif"] / nb_renseignees * 100
    ).round(2)

    frequences = frequences.rename(
        columns={"Valeur": "Valeur observée"}
    )

    st.dataframe(
        frequences,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Les pourcentages sont calculés sur les valeurs renseignées. "
        "Les valeurs manquantes sont comptabilisées séparément."
    )

    csv_frequences = frequences.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        label="Télécharger le tableau des fréquences",
        data=csv_frequences,
        file_name="frequences_" + str(colonne_unique) + ".csv",
        mime="text/csv",
        key="export_frequences"
    )

else:
    st.warning(
        "Cette colonne ne contient aucune valeur renseignée."
    )

# --------------------------------------------------
# 8. VISUALISATION INTERACTIVE
# --------------------------------------------------

st.header("8. Visualisation interactive")
st.write(
    "Choisissez un type de graphique, puis sélectionnez "
    "les colonnes à représenter."
)

types_graphiques = [
    "Histogramme",
    "Boîte à moustaches (Boxplot)",
    "Graphique en barres",
    "Nuage de points",
    "Courbe",
    "Matrice de corrélation (Heatmap)",
    "Diagramme circulaire",
    "Diagramme en violon"
]

type_graphique = st.selectbox(
    "Type de graphique",
    options=types_graphiques
)

graphique = None

# Histogramme
if type_graphique == "Histogramme":
    if not colonnes_numeriques:
        st.info("Ce graphique nécessite une colonne numérique.")
    else:
        x = st.selectbox("Variable numérique", colonnes_numeriques)
        nb_bins = st.slider(
            "Nombre d'intervalles",
            min_value=5,
            max_value=100,
            value=30
        )

        donnees = df[[x]].dropna()
        if not donnees.empty:
            graphique = px.histogram(
                donnees,
                x=x,
                nbins=nb_bins,
                title=f"Distribution de {x}",
                labels={x: x},
                template="plotly_white"
            )

# Boxplot
elif type_graphique == "Boîte à moustaches (Boxplot)":
    if not colonnes_numeriques:
        st.info("Ce graphique nécessite une colonne numérique.")
    else:
        y = st.selectbox("Variable numérique", colonnes_numeriques)
        options_categorie = ["Aucune"] + colonnes_textuelles
        categorie = st.selectbox(
            "Comparer par catégorie (facultatif)",
            options_categorie
        )

        if categorie == "Aucune":
            graphique = px.box(
                df,
                y=y,
                points="outliers",
                title=f"Distribution et valeurs potentiellement aberrantes : {y}",
                template="plotly_white"
            )
        else:
            graphique = px.box(
                df,
                x=categorie,
                y=y,
                points="outliers",
                title=f"{y} selon {categorie}",
                template="plotly_white"
            )

# Graphique en barres
elif type_graphique == "Graphique en barres":
    if not colonnes_textuelles:
        st.info("Ce graphique nécessite une colonne catégorielle.")
    else:
        categorie = st.selectbox("Catégorie", colonnes_textuelles)
        comptage = (
            df[categorie]
            .fillna("(Valeur manquante)")
            .astype(str)
            .value_counts()
            .head(30)
            .rename_axis(categorie)
            .reset_index(name="Effectif")
        )

        graphique = px.bar(
            comptage,
            x=categorie,
            y="Effectif",
            title=f"Effectifs par {categorie} (30 catégories maximum)",
            template="plotly_white"
        )

# Nuage de points
elif type_graphique == "Nuage de points":
    if len(colonnes_numeriques) < 2:
        st.info("Ce graphique nécessite au moins deux colonnes numériques.")
    else:
        col_x, col_y = st.columns(2)

        with col_x:
            x = st.selectbox(
                "Variable sur l'axe X",
                colonnes_numeriques,
                key="scatter_x"
            )

        with col_y:
            y = st.selectbox(
                "Variable sur l'axe Y",
                colonnes_numeriques,
                index=1 if len(colonnes_numeriques) > 1 else 0,
                key="scatter_y"
            )

        couleur = st.selectbox(
            "Colorer les points par catégorie (facultatif)",
            ["Aucune"] + colonnes_textuelles
        )

        if x != y:
            colonnes_a_garder = [x, y]
            if couleur != "Aucune":
                colonnes_a_garder.append(couleur)

            donnees = df[colonnes_a_garder].dropna(subset=[x, y])

            if couleur == "Aucune":
                graphique = px.scatter(
                    donnees,
                    x=x,
                    y=y,
                    title=f"Relation entre {x} et {y}",
                    template="plotly_white"
                )
            else:
                graphique = px.scatter(
                    donnees,
                    x=x,
                    y=y,
                    color=couleur,
                    title=f"{y} en fonction de {x}",
                    template="plotly_white"
                )
        else:
            st.warning("Choisissez deux variables différentes.")

# Courbe
elif type_graphique == "Courbe":
    if not colonnes_numeriques:
        st.info("Ce graphique nécessite une colonne numérique.")
    else:
        x_options = df.columns.tolist()
        x = st.selectbox("Axe X", x_options)
        y = st.selectbox("Axe Y (numérique)", colonnes_numeriques)

        donnees = df[[x, y]].dropna()

        if not donnees.empty:
            graphique = px.line(
                donnees,
                x=x,
                y=y,
                title=f"Évolution de {y} selon {x}",
                markers=True,
                template="plotly_white"
            )

# Heatmap de corrélation
elif type_graphique == "Matrice de corrélation (Heatmap)":
    if len(colonnes_numeriques) < 2:
        st.info(
            "La matrice de corrélation nécessite au moins "
            "deux colonnes numériques."
        )
    else:
        methode = st.selectbox(
            "Méthode de corrélation",
            ["pearson", "spearman", "kendall"]
        )

        correlation = df[colonnes_numeriques].corr(method=methode)

        graphique = px.imshow(
            correlation,
            text_auto=".2f",
            aspect="auto",
            zmin=-1,
            zmax=1,
            color_continuous_scale="RdBu_r",
            title=f"Matrice de corrélation ({methode})",
            template="plotly_white"
        )

        st.caption(
            "Une corrélation mesure une association, pas une relation "
            "de cause à effet. Les corrélations peuvent être influencées "
            "par les valeurs manquantes et les valeurs extrêmes."
        )

# Diagramme circulaire
elif type_graphique == "Diagramme circulaire":
    if not colonnes_textuelles:
        st.info("Ce graphique nécessite une colonne catégorielle.")
    else:
        categorie = st.selectbox(
            "Catégorie à représenter",
            colonnes_textuelles
        )

        comptage = (
            df[categorie]
            .fillna("(Valeur manquante)")
            .astype(str)
            .value_counts()
            .head(10)
            .rename_axis(categorie)
            .reset_index(name="Effectif")
        )

        graphique = px.pie(
            comptage,
            names=categorie,
            values="Effectif",
            title=f"Répartition de {categorie} (10 catégories maximum)",
            template="plotly_white"
        )

        st.caption(
            "Les catégories au-delà des 10 plus fréquentes ne sont pas "
            "représentées dans ce graphique."
        )

# Diagramme en violon
elif type_graphique == "Diagramme en violon":
    if not colonnes_numeriques:
        st.info("Ce graphique nécessite une colonne numérique.")
    else:
        y = st.selectbox("Variable numérique", colonnes_numeriques)
        categorie = st.selectbox(
            "Grouper par catégorie (facultatif)",
            ["Aucune"] + colonnes_textuelles
        )

        if categorie == "Aucune":
            graphique = px.violin(
                df,
                y=y,
                box=True,
                points="outliers",
                title=f"Distribution de {y}",
                template="plotly_white"
            )
        else:
            graphique = px.violin(
                df,
                x=categorie,
                y=y,
                box=True,
                points="outliers",
                title=f"Distribution de {y} par {categorie}",
                template="plotly_white"
            )

# Affichage du graphique
if graphique is not None:
    st.plotly_chart(graphique, use_container_width=True)

# --------------------------------------------------
# --------------------------------------------------
# 9.1 SUPPRESSION, VERIFICATION ET EXPORT DES DOUBLONS
# --------------------------------------------------

st.header("9. Nettoyage des données")
st.subheader("9.1 Gestion des doublons")

# Initialiser la copie de travail
if "df_nettoye" not in st.session_state:
    st.session_state["df_nettoye"] = df.copy()

df_travail = st.session_state["df_nettoye"]

st.write(
    "Supprimez les doublons, vérifiez le résultat, "
    "puis téléchargez le fichier nettoyé."
)

# --------------------------------------------------
# A. RECHERCHE DES DOUBLONS
# --------------------------------------------------

st.subheader("A. Détecter et supprimer les doublons")

type_doublons = st.radio(
    "Type de doublons à rechercher",
    [
        "Doublons exacts (toutes les colonnes)",
        "Doublons selon certaines colonnes"
    ],
    key="type_doublons"
)

if type_doublons == "Doublons exacts (toutes les colonnes)":
    colonnes_comparaison = df_travail.columns.tolist()
else:
    colonnes_comparaison = st.multiselect(
        "Choisissez les colonnes de comparaison",
        options=df_travail.columns.tolist(),
        key="colonnes_doublons"
    )

regle_doublons = st.selectbox(
    "Quelle occurrence conserver ?",
    [
        "Conserver la première",
        "Conserver la dernière",
        "Supprimer toutes les occurrences dupliquées"
    ],
    key="regle_doublons"
)

if colonnes_comparaison:

    masque_groupes = df_travail.duplicated(
        subset=colonnes_comparaison,
        keep=False
    )

    lignes_doublons = df_travail.loc[masque_groupes]

    if regle_doublons == "Conserver la première":
        masque_suppression = df_travail.duplicated(
            subset=colonnes_comparaison,
            keep="first"
        )
    elif regle_doublons == "Conserver la dernière":
        masque_suppression = df_travail.duplicated(
            subset=colonnes_comparaison,
            keep="last"
        )
    else:
        masque_suppression = masque_groupes

    nb_groupes_lignes = int(masque_groupes.sum())
    nb_a_supprimer = int(masque_suppression.sum())

    col1, col2 = st.columns(2)
    col1.metric("Lignes concernées", nb_groupes_lignes)
    col2.metric("Lignes à supprimer", nb_a_supprimer)

    if not lignes_doublons.empty:
        st.write("Aperçu des lignes concernées :")
        st.dataframe(
            lignes_doublons,
            use_container_width=True,
            hide_index=True
        )

    if nb_a_supprimer > 0:

        confirmation = st.checkbox(
            "Je confirme la suppression des lignes affichées.",
            key="confirmation_doublons"
        )

        if st.button(
            "Appliquer la suppression",
            key="appliquer_doublons"
        ):
            if confirmation:
                df_apres = df_travail.loc[
                    ~masque_suppression
                ].copy()

                st.session_state["df_nettoye"] = df_apres

                # Une nouvelle vérification sera nécessaire
                st.session_state["doublons_verifies"] = False

                st.success(
                    f"{nb_a_supprimer} ligne(s) supprimée(s)."
                )

                st.rerun()
            else:
                st.warning(
                    "Cochez la case de confirmation avant de continuer."
                )
    else:
        st.success("Aucune ligne à supprimer selon ces critères.")

else:
    st.info("Sélectionnez au moins une colonne.")

# --------------------------------------------------
# B. VERIFICATION APRES NETTOYAGE
# --------------------------------------------------

st.divider()
st.subheader("B. Vérifier les doublons après nettoyage")

if st.button(
    "Vérifier les doublons",
    key="verifier_doublons"
):
    df_verification = st.session_state["df_nettoye"]

    if colonnes_comparaison:
        masque_verification = df_verification.duplicated(
            subset=colonnes_comparaison,
            keep=False
        )

        nb_lignes_restantes = int(masque_verification.sum())

        st.session_state["doublons_verifies"] = True
        st.session_state["nb_doublons_verifies"] = nb_lignes_restantes
        st.session_state["criteres_verifies"] = colonnes_comparaison.copy()

        st.rerun()

if st.session_state.get("doublons_verifies", False):

    nb_restants = st.session_state.get(
        "nb_doublons_verifies", 0
    )

    if nb_restants == 0:
        st.success(
            "Vérification réussie : aucun doublon ne reste "
            "selon les critères sélectionnés."
        )
    else:
        st.warning(
            f"Vérification terminée : {nb_restants} ligne(s) "
            "appartiennent encore à des groupes de doublons."
        )

        st.dataframe(
            st.session_state["df_nettoye"].loc[
                st.session_state["df_nettoye"].duplicated(
                    subset=st.session_state["criteres_verifies"],
                    keep=False
                )
            ],
            use_container_width=True,
            hide_index=True
        )

# --------------------------------------------------
# C. TELECHARGEMENT DU CSV NETTOYE
# --------------------------------------------------

st.divider()
st.subheader("C. Télécharger le fichier nettoyé")

if st.session_state.get("doublons_verifies", False):

    df_export = st.session_state["df_nettoye"]

    csv_nettoye = df_export.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        label="Télécharger le CSV nettoyé",
        data=csv_nettoye,
        file_name="donnees_nettoyees.csv",
        mime="text/csv",
        key="telecharger_csv_nettoye"
    )

else:
    st.info(
        "Cliquez d'abord sur « Vérifier les doublons » "
        "pour activer le téléchargement."
    )

# --------------------------------------------------
# BILAN
# --------------------------------------------------

st.divider()
st.subheader("Bilan de la copie nettoyée")

df_resultat = st.session_state["df_nettoye"]

col1, col2 = st.columns(2)

col1.metric("Lignes restantes", len(df_resultat))
col2.metric(
    "Doublons exacts restants",
    int(df_resultat.duplicated().sum())
)

st.caption(
    "Le fichier original n'est pas modifié. "
    "Les modifications sont conservées dans la copie de travail "
    " pendant la session de l'application."
)
# --------------------------------------------------
# 9.2 TRAITEMENT DES VALEURS MANQUANTES
# --------------------------------------------------

st.header("9.2 Traitement des valeurs manquantes")

# Récupérer la copie de travail déjà nettoyée des doublons
df_travail = st.session_state["df_nettoye"]

# --------------------------------------------------
# A. ANALYSE DES VALEURS MANQUANTES
# --------------------------------------------------

st.subheader("A. Analyse des valeurs manquantes")

nb_cellules_vides = int(df_travail.isna().sum().sum())

col1, col2 = st.columns(2)

col1.metric("Valeurs manquantes", nb_cellules_vides)
col2.metric(
    "Pourcentage de cellules manquantes",
    f"{df_travail.isna().sum().sum() / df_travail.size * 100:.2f}%"
    if df_travail.size > 0 else "0.00%"
)

analyse_manquants = pd.DataFrame({
    "Colonne": df_travail.columns,
    "Valeurs manquantes": df_travail.isna().sum().values,
    "Pourcentage (%)": (
        df_travail.isna().mean().values * 100
    ).round(2)
})

analyse_manquants = analyse_manquants.sort_values(
    by="Valeurs manquantes",
    ascending=False
)

st.dataframe(
    analyse_manquants,
    use_container_width=True,
    hide_index=True
)

# --------------------------------------------------
# B. CHOIX DE LA COLONNE
# --------------------------------------------------

st.subheader("B. Choisir une colonne")

colonnes_manquantes = df_travail.columns[
    df_travail.isna().any()
].tolist()

if not colonnes_manquantes:

    st.success("Aucune valeur manquante dans le DataFrame de travail.")

else:

    colonne_choisie = st.selectbox(
        "Quelle colonne souhaitez-vous traiter ?",
        options=colonnes_manquantes,
        key="colonne_manquante_choisie"
    )

    serie = df_travail[colonne_choisie]
    nb_manquants_colonne = int(serie.isna().sum())
    pourcentage_manquants = (
        nb_manquants_colonne / len(df_travail) * 100
        if len(df_travail) > 0 else 0
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Colonne sélectionnée", colonne_choisie)
    col2.metric("Valeurs manquantes", nb_manquants_colonne)
    col3.metric("Pourcentage manquant", f"{pourcentage_manquants:.2f}%")

    st.write("Aperçu de la colonne :")

    st.dataframe(
        df_travail[[colonne_choisie]].head(20),
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------
    # C. CHOISIR UNE ACTION
    # --------------------------------------------------

    st.subheader("C. Choisir une action")

    action = st.radio(
        "Que souhaitez-vous faire avec cette colonne ?",
        ["Garder", "Supprimer", "Remplacer"],
        horizontal=True,
        key="action_manquants"
    )

    methode_remplacement = None
    valeur_personnalisee = None
    type_suppression = None
    apercu = df_travail.copy()
    description_action = "Aucune modification"

    # --------------------------------------------------
    # OPTION 1 : GARDER
    # --------------------------------------------------

    if action == "Garder":

        st.info(
            "Les valeurs manquantes de cette colonne seront conservées."
        )

    # --------------------------------------------------
    # OPTION 2 : SUPPRIMER
    # --------------------------------------------------

    elif action == "Supprimer":

        type_suppression = st.radio(
            "Type de suppression",
            [
                "Supprimer les lignes où cette colonne est manquante",
                "Supprimer complètement cette colonne"
            ],
            key="type_suppression_manquants"
        )

        if type_suppression == "Supprimer les lignes où cette colonne est manquante":

            apercu = df_travail.dropna(
                subset=[colonne_choisie]
            ).copy()

            nb_lignes_supprimees = len(df_travail) - len(apercu)

            description_action = (
                f"{nb_lignes_supprimees} ligne(s) seront supprimées."
            )

            st.write("Aperçu après suppression des lignes :")
            st.dataframe(
                apercu.head(20),
                use_container_width=True,
                hide_index=True
            )

            st.metric("Lignes qui seront supprimées", nb_lignes_supprimees)

        else:

            apercu = df_travail.drop(
                columns=[colonne_choisie]
            ).copy()

            description_action = (
                f"La colonne « {colonne_choisie} » sera supprimée."
            )

            st.write("Aperçu après suppression de la colonne :")
            st.dataframe(
                apercu.head(20),
                use_container_width=True,
                hide_index=True
            )

    # --------------------------------------------------
    # OPTION 3 : REMPLACER
    # --------------------------------------------------

    elif action == "Remplacer":

        options_remplacement = [
            "Mode (valeur la plus fréquente)",
            "Valeur précédente",
            "Valeur suivante",
            "Valeur personnalisée"
        ]

        if pd.api.types.is_numeric_dtype(serie):
            options_remplacement = [
                "Moyenne",
                "Médiane"
            ] + options_remplacement

        methode_remplacement = st.selectbox(
            "Méthode de remplacement",
            options=options_remplacement,
            key="methode_remplacement_manquants"
        )

        if methode_remplacement == "Moyenne":

            valeur_remplacement = serie.mean()

            if pd.isna(valeur_remplacement):
                st.warning(
                    "Impossible de calculer la moyenne : "
                    "aucune valeur numérique disponible."
                )
            else:
                apercu[colonne_choisie] = serie.fillna(
                    valeur_remplacement
                )
                description_action = (
                    f"Les valeurs manquantes seront remplacées "
                    f"par la moyenne ({valeur_remplacement:.4g})."
                )

        elif methode_remplacement == "Médiane":

            valeur_remplacement = serie.median()

            if pd.isna(valeur_remplacement):
                st.warning(
                    "Impossible de calculer la médiane : "
                    "aucune valeur disponible."
                )
            else:
                apercu[colonne_choisie] = serie.fillna(
                    valeur_remplacement
                )
                description_action = (
                    f"Les valeurs manquantes seront remplacées "
                    f"par la médiane ({valeur_remplacement:.4g})."
                )

        elif methode_remplacement == "Mode (valeur la plus fréquente)":

            modes = serie.mode(dropna=True)

            if modes.empty:
                st.warning(
                    "Impossible de calculer le mode : "
                    "aucune valeur disponible."
                )
            else:
                valeur_remplacement = modes.iloc[0]
                apercu[colonne_choisie] = serie.fillna(
                    valeur_remplacement
                )
                description_action = (
                    f"Les valeurs manquantes seront remplacées "
                    f"par le mode ({valeur_remplacement})."
                )

        elif methode_remplacement == "Valeur précédente":

            apercu[colonne_choisie] = serie.ffill()
            description_action = (
                "Les valeurs manquantes seront remplacées "
                "par la valeur précédente, si elle existe."
            )

        elif methode_remplacement == "Valeur suivante":

            apercu[colonne_choisie] = serie.bfill()
            description_action = (
                "Les valeurs manquantes seront remplacées "
                "par la valeur suivante, si elle existe."
            )

        elif methode_remplacement == "Valeur personnalisée":

            valeur_saisie = st.text_input(
                "Saisissez la valeur de remplacement",
                key="valeur_personnalisee_manquants"
            )

            if valeur_saisie.strip() != "":

                try:
                    if pd.api.types.is_numeric_dtype(serie):
                        valeur_remplacement = pd.to_numeric(
                            valeur_saisie
                        )
                    else:
                        valeur_remplacement = valeur_saisie

                    apercu[colonne_choisie] = serie.fillna(
                        valeur_remplacement
                    )

                    description_action = (
                        f"Les valeurs manquantes seront remplacées "
                        f"par « {valeur_remplacement} »."
                    )

                except (ValueError, TypeError):
                    st.warning(
                        "La valeur saisie n'est pas compatible "
                        "avec cette colonne."
                    )

        st.write("Aperçu après remplacement :")
        st.dataframe(
            apercu[[colonne_choisie]].head(20),
            use_container_width=True,
            hide_index=True
        )

        st.metric(
            "Valeurs manquantes après traitement",
            int(apercu[colonne_choisie].isna().sum())
        )

    # --------------------------------------------------
    # D. CONFIRMATION ET APPLICATION
    # --------------------------------------------------

    st.subheader("D. Confirmer et appliquer")

    st.write(description_action)

    if action != "Garder":

        confirmation = st.checkbox(
            "Je confirme cette modification.",
            key="confirmation_action_manquants"
        )

        if st.button(
            "Appliquer le traitement",
            key="appliquer_traitement_manquants"
        ):

            if not confirmation:
                st.warning(
                    "Cochez la case de confirmation avant de continuer."
                )

            elif action == "Supprimer":

                st.session_state["df_nettoye"] = apercu.copy()
                st.session_state["doublons_verifies"] = False

                st.success("Suppression appliquée à la copie de travail.")
                st.rerun()

            elif action == "Remplacer":

                if (
                    apercu[colonne_choisie].isna().sum()
                    >= serie.isna().sum()
                    and serie.isna().sum() > 0
                ):
                    st.warning(
                        "Aucune valeur manquante n'a pu être remplacée. "
                        "Vérifiez la méthode choisie et les valeurs disponibles."
                    )
                else:
                    st.session_state["df_nettoye"] = apercu.copy()
                    st.session_state["doublons_verifies"] = False

                    st.success(
                        "Remplacement appliqué à la copie de travail."
                    )
                    st.rerun()

    # --------------------------------------------------
    # E. BILAN
    # --------------------------------------------------

    st.divider()
    st.subheader("E. Bilan après traitement")

    df_resultat = st.session_state["df_nettoye"]

    col1, col2, col3 = st.columns(3)

    col1.metric("Lignes restantes", len(df_resultat))
    col2.metric("Colonnes restantes", len(df_resultat.columns))
    col3.metric(
        "Valeurs manquantes restantes",
        int(df_resultat.isna().sum().sum())
    )
# --------------------------------------------------
# --------------------------------------------------
# 9.3 DETECTION ET TRAITEMENT DES VALEURS ABERRANTES
# --------------------------------------------------

st.header("9.3 Détection et traitement des valeurs aberrantes")

df_travail = st.session_state["df_nettoye"]

st.write(
    "Cette section détecte les valeurs potentiellement aberrantes "
    "avec la méthode IQR. Aucune donnée ne sera modifiée à cette étape."
)

st.info(
    "Une valeur aberrante n'est pas forcément une erreur. "
    "Examinez les résultats avant de décider d'un traitement."
)

# --------------------------------------------------
# A. CHOIX DE LA COLONNE
# --------------------------------------------------

st.subheader("A. Choisir une colonne numérique")

colonnes_numeriques = df_travail.select_dtypes(
    include="number"
).columns.tolist()

if not colonnes_numeriques:

    st.warning("Aucune colonne numérique disponible.")

else:

    colonne_choisie = st.selectbox(
        "Colonne à analyser",
        options=colonnes_numeriques,
        key="colonne_valeurs_aberrantes"
    )

    serie_complete = df_travail[colonne_choisie]

    # Convertir les valeurs en nombres pour l'analyse
    serie = pd.to_numeric(
        serie_complete,
        errors="coerce"
    ).dropna()

    if serie.empty:

        st.warning("Aucune valeur numérique exploitable dans cette colonne.")

    else:

        # --------------------------------------------------
        # B. CALCUL DES BORNES IQR
        # --------------------------------------------------

        st.subheader("B. Résultats de la détection")

        q1 = serie.quantile(0.25)
        q3 = serie.quantile(0.75)
        iqr = q3 - q1

        borne_inferieure = q1 - 1.5 * iqr
        borne_superieure = q3 + 1.5 * iqr

        masque_valide = pd.to_numeric(
            serie_complete,
            errors="coerce"
        ).notna()

        valeurs_numeriques = pd.to_numeric(
            serie_complete,
            errors="coerce"
        )

        masque_aberrantes = (
            masque_valide
            & (
                (valeurs_numeriques < borne_inferieure)
                | (valeurs_numeriques > borne_superieure)
            )
        )

        valeurs_aberrantes = df_travail.loc[
            masque_aberrantes
        ].copy()

        nb_analysees = len(serie)
        nb_aberrantes = int(masque_aberrantes.sum())

        pourcentage_aberrantes = (
            nb_aberrantes / nb_analysees * 100
            if nb_analysees > 0 else 0
        )

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Valeurs analysées",
            nb_analysees
        )

        col2.metric(
            "Valeurs aberrantes détectées",
            nb_aberrantes
        )

        col3.metric(
            "Pourcentage détecté",
            f"{pourcentage_aberrantes:.2f}%"
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Q1", f"{q1:.4g}")
        col2.metric("Q3", f"{q3:.4g}")
        col3.metric("Borne inférieure", f"{borne_inferieure:.4g}")
        col4.metric("Borne supérieure", f"{borne_superieure:.4g}")

        # --------------------------------------------------
        # C. VALEURS EXTREMES DETECTEES
        # --------------------------------------------------

        st.subheader("C. Valeurs extrêmes détectées")

        if nb_aberrantes == 0:

            st.success(
                "Aucune valeur aberrante détectée avec la méthode IQR."
            )

        else:

            valeurs_numeriques_aberrantes = valeurs_numeriques[
                masque_aberrantes
            ]

            col1, col2 = st.columns(2)

            col1.metric(
                "Valeur aberrante minimale",
                f"{valeurs_numeriques_aberrantes.min():.4g}"
            )

            col2.metric(
                "Valeur aberrante maximale",
                f"{valeurs_numeriques_aberrantes.max():.4g}"
            )

            st.write("Lignes contenant des valeurs potentiellement aberrantes :")

            st.dataframe(
                valeurs_aberrantes,
                use_container_width=True,
                hide_index=True
            )

        # --------------------------------------------------
        # D. BOXPLOT
        # --------------------------------------------------

        st.subheader("D. Visualisation avec un boxplot")

        import plotly.express as px

    
        fig = px.box(
            y=serie,
            points="outliers",
            labels={"y": colonne_choisie},
            title=f"Distribution de « {colonne_choisie} »"
        )

        fig.update_layout(
            xaxis_title="",
            yaxis_title=colonne_choisie
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )
    # E. CHOISIR LE TRAITEMENT
    st.markdown("---")
    st.markdown("### E. Choisir le traitement")

    traitement = st.radio(
        "Que souhaites-tu faire avec les valeurs aberrantes ?",
        [
            "Garder les valeurs",
            "Plafonner les valeurs basses et hautes",
            "Supprimer les lignes concernées"
        ],
        key="traitement_aberrantes"
    )

    # Valeurs par défaut : aucune modification
    seuil_bas = borne_inferieure
    seuil_haut = borne_superieure
    masque_bas = pd.Series(False, index=df_travail.index)
    masque_haut = pd.Series(False, index=df_travail.index)
    apercu_aberrantes = df_travail.copy()
    nb_modifications = 0

    # F. CONFIGURER LES SEUILS
    if traitement in [
        "Plafonner les valeurs basses et hautes",
        "Supprimer les lignes concernées"
    ]:
        st.markdown("### F. Définir les seuils")

        col_bas, col_haut = st.columns(2)

        with col_bas:
            st.markdown("#### Seuil inférieur")

            choix_bas = st.selectbox(
                "Comment traiter les valeurs basses ?",
                [
                    "Borne inférieure IQR",
                    "Q1",
                    "Valeur personnalisée",
                    "Garder les valeurs basses telles quelles"
                ],
                key="choix_seuil_bas"
            )

            if choix_bas == "Borne inférieure IQR":
                seuil_bas = float(borne_inferieure)

            elif choix_bas == "Q1":
                seuil_bas = float(q1)

            elif choix_bas == "Valeur personnalisée":
                seuil_bas = st.number_input(
                    "Valeur du seuil inférieur",
                    value=float(borne_inferieure),
                    key="seuil_bas_personnalise"
                )

            else:
                seuil_bas = None

        with col_haut:
            st.markdown("#### Seuil supérieur")

            choix_haut = st.selectbox(
                "Comment traiter les valeurs hautes ?",
                [
                    "Borne supérieure IQR",
                    "Q3",
                    "Valeur personnalisée",
                    "Garder les valeurs hautes telles quelles"
                ],
                key="choix_seuil_haut"
            )

            if choix_haut == "Borne supérieure IQR":
                seuil_haut = float(borne_superieure)

            elif choix_haut == "Q3":
                seuil_haut = float(q3)

            elif choix_haut == "Valeur personnalisée":
                seuil_haut = st.number_input(
                    "Valeur du seuil supérieur",
                    value=float(borne_superieure),
                    key="seuil_haut_personnalise"
                )

            else:
                seuil_haut = None

        # Vérifier la cohérence des seuils sélectionnés
        seuils_valides = True

        if (
            seuil_bas is not None
            and seuil_haut is not None
            and seuil_bas >= seuil_haut
        ):
            st.error(
                "Le seuil inférieur doit être strictement "
                "inférieur au seuil supérieur."
            )
            seuils_valides = False

        # Préparer les modifications sans toucher aux données originales
        if seuils_valides:
            valeurs_numeriques = pd.to_numeric(
                df_travail[colonne_choisie],
                errors="coerce"
            )

            masque_valide = valeurs_numeriques.notna()

            if seuil_bas is not None:
                masque_bas = (
                    masque_valide
                    & (valeurs_numeriques < seuil_bas)
                )

            if seuil_haut is not None:
                masque_haut = (
                    masque_valide
                    & (valeurs_numeriques > seuil_haut)
                )

            masque_a_modifier = masque_bas | masque_haut
            nb_modifications = int(masque_a_modifier.sum())

            st.write(
                f"Nombre de lignes concernées : **{nb_modifications}**"
            )

            if traitement == "Plafonner les valeurs basses et hautes":
                if seuil_bas is not None:
                    apercu_aberrantes.loc[
                        masque_bas, colonne_choisie
                    ] = seuil_bas

                if seuil_haut is not None:
                    apercu_aberrantes.loc[
                        masque_haut, colonne_choisie
                    ] = seuil_haut

            elif traitement == "Supprimer les lignes concernées":
                apercu_aberrantes = df_travail.loc[
                    ~masque_a_modifier
                ].copy()

    else:
        seuils_valides = True
        st.info("Les valeurs seront conservées sans modification.")

# --------------------------------------------------
# H. BILAN DES DONNÉES DE TRAVAIL
# --------------------------------------------------

st.subheader("H. Bilan des données de travail")

# Données originales importées au début
df_initial = st.session_state["df_original"]

# Données après les nettoyages effectués
df_final = st.session_state["df_nettoye"]

# Calcul des indicateurs initiaux
lignes_initiales = len(df_initial)
colonnes_initiales = len(df_initial.columns)
manquants_initiaux = int(df_initial.isna().sum().sum())
doublons_initiaux = int(df_initial.duplicated().sum())

# Calcul des indicateurs actuels
lignes_finales = len(df_final)
colonnes_finales = len(df_final.columns)
manquants_finaux = int(df_final.isna().sum().sum())
doublons_finaux = int(df_final.duplicated().sum())

# Tableau comparatif
bilan = pd.DataFrame({
    "Indicateur": [
        "Nombre de lignes",
        "Nombre de colonnes",
        "Cellules manquantes",
        "Lignes en doublon"
    ],
    "Au début": [
        lignes_initiales,
        colonnes_initiales,
        manquants_initiaux,
        doublons_initiaux
    ],
    "Après nettoyage": [
        lignes_finales,
        colonnes_finales,
        manquants_finaux,
        doublons_finaux
    ],
    "Différence": [
        lignes_finales - lignes_initiales,
        colonnes_finales - colonnes_initiales,
        manquants_finaux - manquants_initiaux,
        doublons_finaux - doublons_initiaux
    ]
})

st.dataframe(bilan, use_container_width=True, hide_index=True)

st.caption(
    "La différence correspond au nombre après nettoyage moins le nombre initial. "
    "Une valeur négative indique une diminution."
)

# --------------------------------------------------
# 10. EXPORT FINAL DES DONNÉES NETTOYÉES
# --------------------------------------------------

st.header("10. Export final des données nettoyées")

st.write(
    "Téléchargez votre fichier CSV final, prêt à être utilisé "
    "dans Power BI, Excel, Python ou un autre outil d'analyse."
)

# Récupérer les données après tous les nettoyages
df_export = st.session_state["df_nettoye"]

# Afficher un résumé du fichier final
col1, col2, col3, col4 = st.columns(4)

col1.metric("Lignes", len(df_export))
col2.metric("Colonnes", len(df_export.columns))
col3.metric(
    "Cellules manquantes",
    int(df_export.isna().sum().sum())
)
col4.metric(
    "Lignes en doublon",
    int(df_export.duplicated().sum())
)

# Préparer le CSV pour le téléchargement
csv_final = df_export.to_csv(
    index=False,
    sep=";",
    encoding="utf-8-sig"
).encode("utf-8-sig")

st.download_button(
    label="📥 Télécharger le CSV final nettoyé",
    data=csv_final,
    file_name="donnees_nettoyees.csv",
    mime="text/csv",
    use_container_width=True
)
