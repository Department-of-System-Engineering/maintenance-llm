from data.raw.vector_store import vector_client


def test_database():
    # 1. Hány elem van benne?
    try:
        db_meret = len(vector_client.db.get()["ids"])
        print(f"📦 ChromaDB mérete: {db_meret} darab chunk\n")
    except Exception as e:
        print(f"❌ Nem tudok csatlakozni az adatbázishoz: {e}")
        return

    # 2. Mit dob ki egy egzakt kódos keresésre?
    teszt_kod = "AB hajó polírozó  hidroakkumulátor nyomásellenőrzés és feltöltés"
    print(f"🔍 Egzakt keresés a következőre: '{teszt_kod}'")

    try:
        eredmenyek = vector_client.db.similarity_search(
            teszt_kod,
            k=3,
            where_document={
                "$or": [
                    {"$contains": teszt_kod},
                    {"$contains": teszt_kod.upper()},
                    {"$contains": teszt_kod.lower()},
                ]
            },
        )

        if not eredmenyek:
            print("❌ NULLA találat! A ChromaDB-ben nincs benne ez a kód.")
            print(
                "Lehetséges ok: A PDF feldolgozó összeolvasztotta a szavakat, vagy kihagyta ezt az oldalt."
            )
        else:
            print(f"✅ {len(eredmenyek)} találat megvan!")
            for i, doc in enumerate(eredmenyek):
                print(f"\n--- {i+1}. TALÁLAT (Nyers adat) ---")
                print(f"📄 Forrás fájl: {doc.metadata.get('source', 'Ismeretlen')}")
                print(f"🏷️ Típus: {doc.metadata.get('type', 'Nincs type metadata')}")
                print(f"📝 Szöveg:\n{doc.page_content.strip()}")
                print("-" * 40)

    except Exception as e:
        print(f"❌ Hiba a keresés során: {e}")


if __name__ == "__main__":
    test_database()
