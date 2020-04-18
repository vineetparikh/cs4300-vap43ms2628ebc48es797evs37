from . import *
from app.irsystem.models.helpers import *
from app.irsystem.models.helpers import NumpyEncoder as NumpyEncoder
from os.path import dirname as up
from collections import defaultdict
from nltk.tokenize import TreebankWordTokenizer
import numpy as np
import math


project_name = "Character Crafter: Turn DnD Concepts to DnD Characters"
net_id = "Vineet Parikh (vap43), Matthew Shih (ms2628), Eli Schmidt (es797), Eric Sunderland(evs37), Eric Chen(ebc48)"


def query_toks_idf_norms(query, idf, tokenizer):
	q_tokens = tokenizer.tokenize(query)
	# Setting up query tf
	query_tf = defaultdict(int)
	for w in set(q_tokens):
		query_tf[w] = q_tokens.count(w)
	# Calculate query norms
	query_norms = 0
	terms = list(idf.keys())
	for t in terms:
		t_idf = idf[t]
		query_norms += math.pow(query_tf[t] * t_idf, 2)
	return q_tokens, query_tf, terms, query_norms


def index_search(query, index, idf, doc_norms, tokenizer):
	""" Search the collection of documents for the given query

    Arguments
    =========

    query: string,
        The query we are looking for.

    index: an inverted index as above

    idf: idf values precomputed as above

    doc_norms: document norms as computed above

    tokenizer: a TreebankWordTokenizer

    Returns
    =======

    results, list of tuples (score, doc_id)
        Sorted list of results such that the first element has
        the highest score, and `doc_id` points to the document
        with the highest score.

    Note:

    """
	n_docs = len(doc_norms)
	results = np.zeros(n_docs)
	answer = []

	q_tokens, query_tf, terms, query_norms = query_toks_idf_norms(query, idf, tokenizer)

	for term in q_tokens:
		if term in terms:
			for doc_num, val in index[term]:
				results[doc_num] += query_tf[term] * val * idf[term] * idf[term]

	for i in range(len(doc_norms)):
		answer.append((results[i] / (math.sqrt(query_norms) * doc_norms[i]), i))
	return sorted(answer, key=lambda x: x[0], reverse=True)


def get_key(search_dict, val):
	for key, value in search_dict.items():
		if val == value:
			return key


def build_inverted_index(msgs, tokenizer):
	inv_idx = defaultdict(list)
	for i, m in enumerate(msgs):
		toks = tokenizer.tokenize(m)
		for w in set(toks):
			inv_idx[w].append((i, toks.count(w)))
	return inv_idx


def compute_idf(inv_idx, n_docs):
	idf = dict()
	for entry in inv_idx.keys():
		len_of_list = len(inv_idx[entry])
		idf[entry] = np.log2(n_docs / (1 + len_of_list))
	return idf


def compute_doc_norms(inv_idx, idf, n_docs):
	doc_norms = np.zeros(n_docs)
	terms = list(idf.keys())
	for t in terms:
		t_idf = idf[t]
		for doc_num,val in inv_idx[t]:
			doc_norms[doc_num] += math.pow(val*t_idf,2)
	return np.sqrt(doc_norms)


@irsystem.route('/', methods=['GET'])
def search():
	query = request.args.get('search')
	if not query:
		data = []
		output_message = ''
	else:
		output_message = "Your search: " + query
		p = 'app/data/classes.json'
		with open(p) as class_file:
			class_data = json.load(class_file)
			class_data = class_data["classes"]
			class_flavor = {}
			class_subclass = {}
			subclass_flavor = {}
			for char_class in class_data:
				class_flavor[char_class["class"]] = char_class["flavor"]
				for subclass_dict in char_class["subclasses"]:
					if char_class["class"] not in class_subclass:
						class_subclass[char_class["class"]] = [subclass_dict["subclass"]]
					else:
						class_subclass[char_class["class"]].append(subclass_dict["subclass"])
					subclass_flavor[subclass_dict["subclass"]] = subclass_dict["flavor"]

		treebank_tokenizer = TreebankWordTokenizer()
		class_flavor_list = list(class_flavor.values())
		inv_idx = build_inverted_index(class_flavor_list, treebank_tokenizer)
		idf = compute_idf(inv_idx, len(class_flavor_list))
		doc_norms = compute_doc_norms(inv_idx, idf, len(class_flavor_list))
		class_results = index_search(query, inv_idx, idf, doc_norms, treebank_tokenizer)

		q_tokens, query_tf, terms, query_norms = query_toks_idf_norms(query, idf, treebank_tokenizer)
		fin_sub_class_results = []
		for score, doc_id in class_results:
			class_list = list(class_flavor.keys())
			subclass_list = class_subclass.get(class_list[doc_id])
			sc_flavors = []
			for sc in subclass_list:
				sc_flavors.append(subclass_flavor.get(sc))
			sc_inv_idx = build_inverted_index(sc_flavors, treebank_tokenizer)
			sc_len = len(sc_flavors)
			sc_idf = compute_idf(sc_inv_idx, sc_len)
			sc_doc_norms = compute_doc_norms(sc_inv_idx, sc_idf, sc_len)
			n_docs = len(sc_doc_norms)
			results = np.zeros(n_docs)
			sc_results = []
			for term in q_tokens:
				if term in terms:
					for doc_num, val in sc_inv_idx[term]:
						results[doc_num] += query_tf[term] * val * sc_idf[term] * sc_idf[term]
			for i in range(len(sc_doc_norms)):
				sc_results.append((results[i] / (math.sqrt(query_norms) * sc_doc_norms[i]), i))
			for res, ind in sc_results:
				fin_sub_class_results.append((score+res, class_list[doc_id] + ": " + subclass_list[ind]))
			fin_sub_class_results = sorted(fin_sub_class_results, key=lambda x: x[0], reverse=True)

		results = [res_class for score, res_class in fin_sub_class_results]
		data = results
	return render_template('search.html', name=project_name, netid=net_id, output_message=output_message, data=data)
