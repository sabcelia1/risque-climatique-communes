"""Page « Assistant » : une question en français, une requête SQL vérifiée, une réponse contrôlée."""

import streamlit as st

import donnees as d

EXEMPLES = [
    "Quelles sont les 10 communes du Gers les plus exposées à la sécheresse à 5 ans ?",
    "Quel département compte le plus de reconnaissances pour inondation depuis 2015 ?",
    "Combien de communes ont plus de la moitié de leur territoire en exposition forte aux argiles ?",
    "Quel est le délai médian de reconnaissance d'une sécheresse, par année, depuis 2015 ?",
]


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def repondre(question: str) -> dict:
    from assistant_sql import repondre as repondre_sql
    r = repondre_sql(d.gemini(), d.base(avec_facteurs=False).cursor(), question)
    return r


def page():
    st.title("Interroger les données en français")
    st.caption("Gemini traduit la question en SQL. La requête n'est exécutée qu'après des garde-fous : lecture "
               "seule, tables du projet uniquement, aucun accès aux fichiers, durée et nombre de lignes plafonnés. "
               "Le résumé n'est affiché que si ses chiffres figurent dans le résultat.")
    if not d.cle_gemini_disponible():
        st.info("L'assistant n'est pas activé sur cette installation (clé Gemini absente).")
        return
    cols = st.columns(2)
    for i, exemple in enumerate(EXEMPLES):
        if cols[i % 2].button(exemple, key=f"ex{i}", width="stretch"):
            st.session_state["question"] = exemple
    question = st.text_input("Votre question", key="question", max_chars=300,
                             placeholder="Ex. : Quelles communes du Var ont eu le plus d'inondations ?")
    if not question:
        return
    if not d.compteur("nb_questions", d.LIMITE_QUESTIONS):
        st.warning(f"Limite de {d.LIMITE_QUESTIONS} questions par visite atteinte (quota gratuit de Gemini).")
        return
    with st.spinner("Traduction en SQL, vérification et exécution…"):
        try:
            r = repondre(question.strip())
        except Exception as e:
            st.error(f"Gemini est indisponible pour le moment ({type(e).__name__}). Réessayez plus tard.")
            return
    if r["sql"]:
        st.markdown("**Requête SQL générée**" + (" (corrigée après une première erreur)" if r.get("corrigee") else ""))
        st.code(r["sql"], language="sql")
    if r["statut"] == "exécutée":
        if r["reponse"]:
            st.success(r["reponse"])
        else:
            st.info("Résumé masqué : il contenait des chiffres absents du résultat. Le tableau ci-dessous fait foi.")
        st.dataframe(r["resultat"], hide_index=True, width="stretch")
    elif r["statut"] == "refus du modèle":
        st.warning(f"Question refusée : {r['explication']}")
    else:
        st.error(f"Requête bloquée : {r['statut'].split(' : ', 1)[-1]}")
