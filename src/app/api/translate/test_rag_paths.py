from chatbot_core import KnowledgeBase


def preview(title: str, text: str, limit: int = 500) -> None:
    print(f"\n=== {title} ===")
    if not text:
        print("EMPTY")
        return
    print(text[:limit])


def main() -> None:
    kb = KnowledgeBase()
    print(f"ready={kb.ready}, atlas_ready={kb._atlas_ready}, vector={kb._atlas_use_vector}")

    query_1 = "Skim Dana Padanan 2026 untuk syarikat PKS"
    query_2 = "Industry 4.0 grant for ERP robotics cloud for SMEs"

    result_1 = kb.retrieve(query_1, top_k=2)
    preview("Query 1", result_1)

    result_2 = kb.retrieve(query_2, top_k=2)
    preview("Query 2", result_2)


if __name__ == "__main__":
    main()
