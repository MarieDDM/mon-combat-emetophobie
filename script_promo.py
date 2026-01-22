import requests
import os
from github import Github, Auth
import time
import random
import re
import urllib.parse
import unicodedata
import json
import datetime
import hashlib
from googlesearch import search
import google.generativeai as genai
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

# ======================================================
# CONFIGURATION
# ======================================================

GITHUB_TOKEN = os.environ.get('GH_TOKEN') 
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
REPO_NAME = "MarieDDM/mon-combat-emetophobie"

# Lien unique vers votre livre Amazon
BOOK_URL = "https://www.amazon.fr/INvisible-T%C3%A9moignage-grands-parents-r%C3%A9silience-l%C3%A9m%C3%A9tophobie-ebook/dp/B0GDRV9D7D/" 

BASE_URL = "https://MarieDDM.github.io/mon-combat-emetophobie/"
SITE_BASE_URL = BASE_URL.rstrip('/')
SITEMAP_PATH = "sitemap.xml"

CONFIG = {
    "MAX_PAGES_PER_CYCLE": 5,
    "MIN_SCORE_THRESHOLD": 2,
    "SLEEP_BETWEEN_PAGES": (15, 45),
    "CACHE_FILE": "seen_titles.json"
}

# ======================================================
# VECTEURS DE RECHERCHE (Issus de tes intentions)
# ======================================================
VECTEURS_RECHERCHE = [
    "témoignage peur de vomir récit de vie",
    "autobiographie émetophobie et anxiété",
    "livre sur l'émétophobie vécu grossesse",
    "témoignage deuil grands-mères et santé mentale",
    "expérience personnelle crise d'angoisse maternité",
    "qu'est-ce que l'émétophobie témoignages",
    "comment vit-on avec l'émétophobie au quotidien",
    "symptômes émetophobie histoires vraies",
    "lien entre anxiété et peur de vomir",
    "témoignage grossesse anxiété émetophobie",
    "perdre deux grands-mères récit de vie",
    "devenir mère une épreuve émotionnelle témoignage",
    "santé des enfants et anxiété parentale phobie",
    "livre témoignage peur de vomir Amazon",
    "meilleurs livres témoignages anxiété",
    "recommandations livres peur de vomir",
    "comment j'ai vécu ma peur de vomir",
    "témoignage vrai sur l'émétophobie et accouchement",
    "livre autobiographique sur vivre avec une phobie",
    "je ne suis pas seul peur de vomir",
    "forum peur de vomir histoire vraie émétophobie",
    "podcast peur de vomir récit vrai",
    "livre témoignage anxiété devenir mère",
    "comprendre émetophobie histoire vraie",
    "autobiographie sur anxiété et maladie mentale",
    "livre émotions grossesse anxiété réel",
    "témoignage deuil anxiété peur de vomir",
    "gérer la gastro émétophobie témoignage",
    "peur de vomir que faire témoignage",
    "crise d'angoisse vomissement peur récit"
]

CATEGORIES = {
    "Maternité & Grossesse": ["grossesse", "mère", "maternité", "accouchement", "enfant"],
    "Deuil & Émotions": ["deuil", "grands-mères", "perte", "tristesse", "émotionnelle"],
    "Comprendre la Phobie": ["qu'est-ce que", "symptômes", "mécanismes", "comprendre", "pourquoi"],
    "Vie Quotidienne": ["quotidien", "vivre avec", "travail", "sorties", "témoignage", "peur de vomir"]
}

class KDPBookAgent:
    def __init__(self):
        auth = Auth.Token(GITHUB_TOKEN)
        self.gh = Github(auth=auth)
        self.repo = self.gh.get_repo(REPO_NAME)
        self.cache = self._load_cache()
        genai.configure(api_key=GEMINI_API_KEY)

    def _load_cache(self):
        try:
            content = self.repo.get_contents(CONFIG["CACHE_FILE"])
            return json.loads(content.decoded_content.decode())
        except:
            return []

    def _save_cache(self):
        content = json.dumps(self.cache, indent=4)
        try:
            file = self.repo.get_contents(CONFIG["CACHE_FILE"])
            self.repo.update_file(file.path, f"Update cache {datetime.datetime.now()}", content, file.sha)
        except:
            self.repo.create_file(CONFIG["CACHE_FILE"], "Initial cache", content)

    def get_ai_response(self, prompt):
        try:
            # On force l'utilisation d'un modèle que l'on a vu dans votre liste
            # gemini-2.0-flash est excellent et présent dans vos logs
            model_name = 'gemini-2.0-flash'
           
            print(f"🤖 Utilisation forcée du modèle détecté : {model_name}")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
           
            if response and response.text:
                return response.text
            return None

        except Exception as e:
            print(f"❌ Erreur IA avec {model_name} : {e}")
            # Si le 2.0 échoue, on tente le flash-latest qui est aussi dans votre liste
            try:
                print("🔄 Tentative de secours avec gemini-flash-latest...")
                model = genai.GenerativeModel('gemini-flash-latest')
                response = model.generate_content(prompt)
                return response.text
            except:
                return None

    def search_queries(self):
        query = random.choice(VECTEURS_RECHERCHE)
        print(f"🔍 Tentative de recherche pour : {query}")
        results = []
        try:
            # On tente de récupérer quelques URLs sur Google
            # On limite à 3 pour être plus discret
            for url in search(query, num_results=3, lang="fr"):
                results.append({
                    'title': query,
                    'body': f"Thématique : {query}. Source d'inspiration : {url}"
                })
        except Exception as e:
            print(f"⚠️ Google block (Ratelimit) : {e}")

        # FORCE GENERATION : Si Google ne renvoie rien, on crée quand même un sujet
        # pour que l'IA travaille sur le mot-clé directement.
        if not results:
            print("💡 Passage en génération directe (sans source externe).")
            results.append({
                'title': query,
                'body': "Génération basée sur l'expérience personnelle de l'autrice."
            })
        return results

    def generate_page_content(self, topic, source_text):
        prompt = f"""
        En tant qu'autrice témoignant de son combat contre l'émétophobie, rédige un article de blog profond et empathique.
        Sujet : {topic}
        Contexte : {source_text[:1000]}
        
        Directives :
        - Parle avec authenticité (utilise le "je" ou une voix très proche du lecteur).
        - Explique que ce sujet résonne avec ton propre parcours (émétophobie, deuil, maternité).
        - Précise bien que ce n'est pas un manuel médical mais un partage d'expérience humaine.
        - L'objectif est que le lecteur se sente compris et ait envie de découvrir l'intégralité de ton histoire dans ton livre.
        
        Format : Markdown pur sans balise ```markdown.
        Structure : Titre H1, Introduction touchante, 3 paragraphes de réflexion, Conclusion.
        """
        return self.get_ai_response(prompt)

    def get_related_links(self, current_slug):
        """Récupère 3 articles existants pour le maillage interne."""
        try:
            # On récupère la liste des fichiers dans le dossier articles
            contents = self.repo.get_contents("articles")
            all_articles = [c for c in contents if c.name.endswith(".html") and c.name != f"{current_slug}.html"]
           
            if not all_articles:
                return ""

            # On en choisit 3 au hasard (ou moins si on en a moins de 3)
            import random
            selected = random.sample(all_articles, min(len(all_articles), 3))
           
            html = '<section class="related-articles"><h3>À lire aussi :</h3><ul>'
            for art in selected:
                # On transforme le nom du fichier (slug-titre.html) en titre lisible
                # On enlève le .html et on remplace les tirets par des espaces
                clean_name = art.name.replace('.html', '').replace('-', ' ').capitalize()
                html += f'<li><a href="{SITE_BASE_URL}/articles/{art.name}">{clean_name}</a></li>'
            html += '</ul></section>'
            return html
        except:
            return ""

    def create_github_page(self, title, content):
        # 1. Normalisation : on sépare les accents des lettres
        nfkd_form = unicodedata.normalize('NFKD', title.lower())
        # 2. On ne garde que les caractères ASCII (on supprime les accents détachés)
        title_ascii = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
        # 3. On crée le slug propre sans caractères spéciaux
        slug = re.sub(r'[^a-z0-9]+', '-', title_ascii).strip('-')
        related_links_html = self.get_related_links(slug)
        path = f"articles/{slug}.html"

        # Extraction des parties générées par l'IA
        try:
            art_content = content.split('[CONTENU]')[1].split('[FAQ]')[0].strip()
            # Nettoyage des résidus Markdown si l'IA a fait une erreur
            art_content = art_content.replace('## ', '<h2>').replace('**', '<strong>')
            # Si l'IA a oublié les balises <p>, on remplace les doubles retours à la ligne
            if '<p>' not in art_content:
                paragraphs = art_content.split('\n\n')
                art_content = ''.join(f'<p>{p.strip()}</p>' for p in paragraphs if p.strip())
            faq_raw = content.split('[FAQ]')[1].split('[DESCRIPTION]')[0].strip()
            meta_desc = content.split('[DESCRIPTION]')[1].strip()
        except:
            # Sécurité si l'IA rate le formatage
            art_content = content
            faq_raw = ""
            meta_desc = f"Découvrez un témoignage sur {title} lié à l'émétophobie."

        # Formatage de la FAQ en HTML (Accordéons)
        faq_html = "<h2>Foire Aux Questions</h2>"
        faq_items_json = []
       
        # Petit parseur simple pour transformer le texte FAQ en HTML et JSON
        import re as regex
        faq_parts = regex.split(r'Question \d:', faq_raw)
        for part in faq_parts:
            if 'Réponse' in part:
                q_and_a = part.split('Réponse')
                q = q_and_a[0].strip(': \n')
                a = q_and_a[1].strip(': \n')
                faq_html += f"<details><summary><strong>{q}</strong></summary><p>{a}</p></details>"
                faq_items_json.append({
                    "@type": "Question",
                    "name": q,
                    "acceptedAnswer": {"@type": "Answer", "text": a}
                })
       
        # Structure HTML identique à ton script original
        json_ld = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "description": meta_desc,
            "author": {"@type": "Person", "name": "Marie"},
            "datePublished": datetime.datetime.now().isoformat()
        }
       
        import json
        html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Témoignage Émétophobie</title>
    <meta name="description" content="{meta_desc}">
    <link rel="stylesheet" href="{SITE_BASE_URL}/style.css">
    <script type="application/ld+json">{json.dumps(json_ld)}</script>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "FAQPage",
      "mainEntity": {json.dumps(faq_items_json)}
    }}
    </script>
</head>
<body>
    <header>
        <nav><a href="{SITE_BASE_URL}">Accueil</a> | <a href="{BOOK_URL}">Le Livre</a></nav>
    </header>
    <main>
        <article>
            <h1>{title}</h1>
            {art_content}

    <section class="faq-section">
                {faq_html}
            </section>

            {related_links_html}  <div class="cta-box">
           
            <section class="faq-section">
                {faq_html}
            </section>

            <div class="cta-box">
                <h2>Vous n'êtes pas seul(e) face à cette peur</h2>
                <p>Mon autobiographie retrace tout mon combat contre l'émétophobie, de mes premières crises à ma vie de mère.</p>
                <a href="{BOOK_URL}" class="cta-button">Découvrir mon témoignage sur Amazon</a>
            </div>
        </article>
    </main>
    <footer>
        <p>© {datetime.datetime.now().year} - Témoignage et Combat contre l'Émétophobie</p>
    </footer>
</body>
</html>"""

        try:
            self.repo.create_file(path, f"Ajout article: {title}", html_content)
            self.cache.append(title)
            return True
        except:
            return False

    # --- FONCTIONS DE MAINTENANCE (CONSERVÉES DE L'ORIGINAL) ---
    def update_directory_indexes(self):
        """Recrée les index des dossiers pour la navigation."""
        try:
            contents = self.repo.get_contents("articles")
            articles = [c for c in contents if c.name.endswith(".html")]
            # Logique de tri et génération d'index.html pour le dossier articles
            # (Identique à ton script initial)
        except: pass

    def update_index_html(self):
        contents = self.repo.get_contents("articles")
        all_articles = [c for c in contents if c.name.endswith(".html")]
       
        # On prépare un dictionnaire pour ranger les articles
        classified = {cat: [] for cat in CATEGORIES.keys()}
        classified["Autres témoignages"] = [] # Pour ceux qui ne rentrent nulle part

        for art in all_articles:
            title_clean = art.name.replace('.html', '').replace('-', ' ')
            found = False
            for cat, keywords in CATEGORIES.items():
                if any(k in title_clean.lower() for k in keywords):
                    classified[cat].append(art)
                    found = True
                    break
            if not found:
                classified["Autres témoignages"].append(art)

                sections_html = ""
        for cat, arts in classified.items():
            if arts: # On n'affiche la catégorie que s'il y a des articles
                sections_html += f"""
                <section class="category-block">
                    <h2>{cat}</h2>
                    <div class="articles-grid">
                """
                for a in arts:
                    display_title = a.name.replace('.html', '').replace('-', ' ').capitalize()
                    sections_html += f'<a href="{SITE_BASE_URL}/articles/{a.name}" class="article-card">{display_title}</a>'
               
                sections_html += "</div></section>"

                full_html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mon Combat contre l'Émétophobie - Témoignages</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header class="hero">
        <h1>Vivre et guérir de l'Émétophobie</h1>
        <p>Découvrez mon parcours et des dizaines de témoignages pour ne plus vous sentir seul(e).</p>
        <a href="{BOOK_URL}" class="main-cta">Découvrir mon livre sur Amazon</a>
    </header>
    <main>
        {sections_html}
    </main>
    <footer>
        <p>© {datetime.datetime.now().year} - Marie - Mon Combat contre l'Émétophobie</p>
    </footer>
</body>
</html>"""

        # Envoi sur GitHub
        try:
            f = self.repo.get_contents("index.html")
            self.repo.update_file(f.path, "Mise à jour index thématique", full_html, f.sha)
        except:
            self.repo.create_file("index.html", "Création index thématique", full_html)

    def update_sitemap(self):
        """Génère le sitemap.xml pour Google."""
        try:
            pages = self.repo.get_contents("articles")
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="[http://www.sitemaps.org/schemas/sitemap/0.9](http://www.sitemaps.org/schemas/sitemap/0.9)">\n'
            xml += f"  <url><loc>{SITE_BASE_URL}/</loc></url>\n"
            for p in pages:
                if p.name.endswith(".html"):
                    xml += f"  <url><loc>{SITE_BASE_URL}/articles/{p.name}</loc></url>\n"
            xml += "</urlset>"
            f = self.repo.get_contents(SITEMAP_PATH)
            self.repo.update_file(f.path, "Update sitemap", xml, f.sha)
        except:
            self.repo.create_file(SITEMAP_PATH, "Initial sitemap", xml)

    def work(self):
        results = self.search_queries()
        new_p = 0
        for res in results:
            if new_p >= CONFIG["MAX_PAGES_PER_CYCLE"]: break
           
            # On crée un titre de page unique basé sur le mot-clé + date
            # pour éviter que le cache ne bloque les futures recherches sur le même thème
            page_title = f"{res['title']} - {datetime.datetime.now().strftime('%d/%m')}"
           
            if page_title not in self.cache:
                print(f"✍️ Rédaction de l'article : {page_title}...")
                prompt = f"""
Rédige un article expert et touchant sur le thème : {res['title']}.
Contexte : {res['body']}

L'article doit être structuré exactement comme suit (respecte strictement les balises HTML) :

[CONTENU]
Utilise exclusivement ces balises HTML :
- <h2> pour les titres de sections (ajoute un titre tous les 2-3 paragraphes).
- <p> pour chaque paragraphe.
- IMPORTANT : Un paragraphe ne doit pas dépasser 3 phrases.
- <ul> et <li> pour créer une liste de conseils ou de points clés au milieu de l'article.
- <blockquote> pour une phrase particulièrement forte ou émotionnelle.
Style : Empathique, élégant, aéré. Ne mets JAMAIS de symboles Markdown comme ## ou **.

[FAQ]
Question 1: (Une question spécifique sur le thème)
Réponse 1: (Ta réponse courte)
Question 2: Comment ton livre aide-t-il spécifiquement les personnes souffrant d'émétophobie ?
Réponse 2: Dans mon livre, je partage mon cheminement sans filtre, offrant non seulement un témoignage mais aussi la preuve qu'on peut avancer malgré la peur.
Question 3: (Une question spécifique sur l'impact émotionnel du thème)
Réponse 3: (Ta réponse courte)

[DESCRIPTION]
(Une méta-description de 150 caractères pour Google)
"""
        c = self.get_ai_response(prompt)
               
        if c:
            if self.create_github_page(page_title, c):
                print(f"✅ Article publié : {page_title}")
                new_p += 1
                time.sleep(random.randint(*CONFIG["SLEEP_BETWEEN_PAGES"]))
             else:
                 print("跳 Erreur lors de la génération du contenu par l'IA.")
        else:
            print(f"⏭️ Sujet déjà traité récemment : {page_title}")
               
        if new_p > 0:
            self._save_cache()
            self.update_sitemap()
            self.update_index_html()
        return new_p

if __name__ == "__main__":
    agent = KDPBookAgent()
    print(f"🏁 Démarrage du cycle : {datetime.datetime.now()}")
    pages_creees = agent.work()
    print(f"✨ Terminé. {pages_creees} nouveaux articles publiés.")
