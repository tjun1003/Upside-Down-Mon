import argparse
import time
from typing import Any, Dict, List

from pymongo import MongoClient, UpdateOne
from pymongo.operations import SearchIndexModel

from translation_config import (
	ATLAS_COLLECTION_NAME,
	ATLAS_DB_NAME,
	ATLAS_EMBEDDING_FIELD,
	ATLAS_TEXT_FIELD,
	ATLAS_URI,
	ATLAS_VECTOR_INDEX,
	logger,
)


def chunked(items: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
	return [items[i : i + size] for i in range(0, len(items), size)]


def create_embedder():
	from llama_index.embeddings.huggingface import HuggingFaceEmbedding

	return HuggingFaceEmbedding(model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2")


def ensure_vector_index(collection, dimensions: int, wait_timeout: int = 180) -> None:
	definition = {
		"fields": [
			{
				"type": "vector",
				"path": ATLAS_EMBEDDING_FIELD,
				"numDimensions": dimensions,
				"similarity": "cosine",
			}
		]
	}

	existing = {index["name"]: index for index in collection.list_search_indexes()}
	if ATLAS_VECTOR_INDEX in existing:
		collection.update_search_index(ATLAS_VECTOR_INDEX, definition)
		logger.info(f"Updated Atlas vector index: {ATLAS_VECTOR_INDEX}")
	else:
		model = SearchIndexModel(
			definition=definition,
			name=ATLAS_VECTOR_INDEX,
			type="vectorSearch",
		)
		collection.create_search_index(model)
		logger.info(f"Created Atlas vector index: {ATLAS_VECTOR_INDEX}")

	deadline = time.time() + wait_timeout
	while time.time() < deadline:
		indexes = {index["name"]: index for index in collection.list_search_indexes()}
		current = indexes.get(ATLAS_VECTOR_INDEX)
		if current and current.get("queryable") and current.get("status") == "READY":
			logger.info(f"Atlas vector index is READY: {ATLAS_VECTOR_INDEX}")
			return
		time.sleep(5)

	raise TimeoutError(f"Timed out waiting for Atlas vector index {ATLAS_VECTOR_INDEX} to become READY")


def backfill_embeddings(force: bool = False, batch_size: int = 16) -> int:
	if not ATLAS_URI or not ATLAS_DB_NAME:
		raise RuntimeError("Missing MongoDB Atlas configuration in environment")

	client = MongoClient(ATLAS_URI, appname="atlas-vector-backfill")
	collection = client[ATLAS_DB_NAME][ATLAS_COLLECTION_NAME]
	embedder = create_embedder()

	query: Dict[str, Any] = {
		ATLAS_TEXT_FIELD: {"$type": "string", "$ne": ""},
	}
	if not force:
		query[ATLAS_EMBEDDING_FIELD] = {"$exists": False}

	docs = list(collection.find(query, {"_id": 1, ATLAS_TEXT_FIELD: 1}))
	if not docs:
		logger.info("No documents require embedding backfill")

		sample = collection.find_one({ATLAS_EMBEDDING_FIELD: {"$exists": True}}, {ATLAS_EMBEDDING_FIELD: 1})
		if not sample or ATLAS_EMBEDDING_FIELD not in sample:
			raise RuntimeError("No embeddings found in the collection; cannot provision vector search")

		ensure_vector_index(collection, len(sample[ATLAS_EMBEDDING_FIELD]))
		return 0

	total_updated = 0
	sample_vector = None
	for batch in chunked(docs, batch_size):
		texts = [str(doc[ATLAS_TEXT_FIELD]).strip() for doc in batch]
		vectors = embedder.get_text_embedding_batch(texts)
		sample_vector = sample_vector or vectors[0]

		operations = [
			UpdateOne(
				{"_id": doc["_id"]},
				{"$set": {ATLAS_EMBEDDING_FIELD: vector}},
			)
			for doc, vector in zip(batch, vectors)
		]
		result = collection.bulk_write(operations, ordered=False)
		total_updated += result.modified_count
		logger.info(f"Backfilled embeddings for {total_updated}/{len(docs)} documents")

	if sample_vector is None:
		raise RuntimeError("Embedding generation failed; no vectors produced")

	ensure_vector_index(collection, len(sample_vector))
	return total_updated


def main() -> None:
	parser = argparse.ArgumentParser(description="Backfill MongoDB Atlas embeddings and create vector search index")
	parser.add_argument("--force", action="store_true", help="Recompute embeddings even if they already exist")
	parser.add_argument("--batch-size", type=int, default=16, help="Embedding batch size")
	args = parser.parse_args()

	updated = backfill_embeddings(force=args.force, batch_size=max(1, args.batch_size))
	logger.info(
		f"Atlas vector backfill complete. Updated {updated} documents. Ready to use index {ATLAS_VECTOR_INDEX}."
	)


if __name__ == "__main__":
	main()
