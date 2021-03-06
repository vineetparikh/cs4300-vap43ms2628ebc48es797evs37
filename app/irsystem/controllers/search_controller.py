from app.irsystem.models.helpers import *
from . import *
import nltk
from nltk import word_tokenize
from nltk.corpus import stopwords

from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse.linalg import svds
from sklearn.preprocessing import normalize
import scipy
import numpy as np
from app.irsystem.controllers.word_forms import get_word_forms
from flask import json

project_name = "Character Crafter: Turn DnD Concepts to DnD Characters"
net_id = "Vineet Parikh (vap43), Matthew Shih (ms2628), Eli Schmidt (es797), Eric Sunderland(evs37), Eric Chen(ebc48)"

def rank_doc_similarity_to_word(word_in, docs, dims):
	np.random.shuffle(docs)
	vectorizer = TfidfVectorizer(stop_words = 'english')
	my_matrix = vectorizer.fit_transform([x[1] for x in docs]).transpose()
	words_compressed, _, docs_compressed = svds(my_matrix, k=dims)
	docs_compressed = docs_compressed.transpose()
	word_to_index = vectorizer.vocabulary_
	index_to_word = {i:t for t,i in word_to_index.items()}
	words_compressed = normalize(words_compressed, axis=1)
	my_matrix_csr = normalize(scipy.sparse.csr_matrix(my_matrix))
	docs_compressed = normalize(docs_compressed, axis = 1)
	def closest_projects_to_word(word_in, word_to_index, k=15):
		if word_in not in word_to_index: return 'not in vocab'
		sims = docs_compressed.dot(words_compressed[word_to_index[word_in],:])
		ssort = np.argsort(-sims)[:k+1]
		return [(docs[i][0],sims[i]/sims[ssort[0]]) for i in ssort[0:]]
	return closest_projects_to_word(word_in, word_to_index)


@irsystem.route('/', methods=['GET', 'POST'])
def search():
	query = request.args.get('search')
	
	if not query:
		data = []
		
		output_message =[]


	else:
		if request.method == 'POST':
			class_name = request.form['class']
			subclass_name= class_name.split(":")[1]
			rating= float(request.form['rating'])
			q1="SELECT overallfreq,combinedrating FROM fullsubclassratings WHERE subclass IN ('"
			q2=q1+subclass_name+"')"
			freq= float([r[0] for r in(db.engine.execute(q2))][0])
			combrating= float([r[1] for r in(db.engine.execute(q2))][0])
			newfreq=freq+1
			newrating = (freq*combrating + rating)/newfreq
			q3="UPDATE fullsubclassratings SET overallfreq=" + str(newfreq) +" WHERE subclass IN('" +subclass_name + "')"
			db.engine.execute(q3)
			db.engine.execute("UPDATE fullsubclassratings SET combinedrating = "+ str(newrating) + " WHERE subclass IN('" + subclass_name +"')")


			
		query = query.lower()
		output_message = query
		p = 'app/data/classes.json'
		with open(p) as class_file:
			f = json.load(class_file)

		cdocs = [(c["class"], (c["flavor"]+c["advice"]))for c in f["classes"]]
		qtokens = word_tokenize(query)
		qtokens = [word for word in qtokens if not word in stopwords.words()]

		inflecs = []
		for w in qtokens:
			inf = get_word_forms(w)
			for k,v in inf.items():
				inflecs.extend(list(v))
		qtokens = list(set(inflecs))

		base_ratings = dict()
		ratings_with_subclasses = dict()
		for c in f["classes"]:
			base_ratings[c["class"]]=0
		for qt in qtokens:
			rezp = rank_doc_similarity_to_word(qt, cdocs, 10)
			if(rezp!='not in vocab'):
				for rp in rezp:
					base_ratings[rp[0]]+=rp[1]
		if(len(qtokens)!=0):
			for k, rating in base_ratings.items():
				base_ratings[k] = rating/len(qtokens)

		for c in f["classes"]:
			for s in c["subclasses"]:
				cs_key = c["class"]+":"+s["subclass"]
				ratings_with_subclasses[cs_key]=0
			sdocs = [(c["class"]+":"+s["subclass"], (s["flavor"]+s["advice"])) for s in c["subclasses"]]
			for qt in qtokens:
				rezp = rank_doc_similarity_to_word(qt, sdocs, 3)
				if(rezp!="not in vocab"):
					for rp in rezp:
						ratings_with_subclasses[rp[0]]+=rp[1]
		if(len(qtokens)!=0):
			for k, rating in ratings_with_subclasses.items():
				base_class = k.split(":")[0] # because that's what we did
				ratings_with_subclasses[k] = (rating/float(len(qtokens))+base_ratings[base_class])/2

		csc_rating_pairs = sorted(list(ratings_with_subclasses.items()),key = lambda x: x[1])
		csc_rating_pairs = list(reversed(csc_rating_pairs))[:10]
		ret = []

		for cscr in csc_rating_pairs:
			base_class = cscr[0].split(":")[0]
			subclass = cscr[0].split(":")[1]
			rating = cscr[1]
			sqlquery="SELECT combinedrating FROM fullsubclassratings WHERE subclass IN ('"
			sqlquery2=subclass
			sqlquery3="')"
			fullquery=sqlquery+sqlquery2+sqlquery3
			socialrating = [r[0] for r in(db.engine.execute(fullquery))]
			if(len(socialrating)==0):
				socialrating=[0]
			flavor_tot = ""
			for c in f["classes"]:
				if c["class"]==base_class:
					flavor_tot+=c["advice"]
					for s in c["subclasses"]:
						if s["subclass"]==subclass:
							flavor_tot+=(s["advice"])
			rdict = dict()
			rdict["class"] = cscr[0]
			rdict["flavor"] = flavor_tot
			rdict["match"] = round(rating*5,2)
			rdict["social"] =socialrating[0]
			rdict["rating"] = rdict["match"]*.75+rdict["social"]*.25
			ret.append(rdict)
		ret.sort(key = lambda x:x["rating"],reverse=True)
		data = ret
	return render_template('search.html', name=project_name, netid=net_id, output_message=output_message, data=data)
