# services/rag_service.py
from data.raw.vector_store import vector_client
from services.llm_service import llm_service
import yaml
import os
import re
from itertools import zip_longest
from datetime import datetime


class RAGService:
    def __init__(self):
        with open("config/prompt.yaml", "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.chat_history = []

    def search_and_chat_w_history(self, user_query: str):
        if len(self.chat_history) > 0:
            history_text = "\n".join(self.chat_history[-4:])

            rewriter_prompt = (
                "Te egy intelligens asszisztens vagy. Olvasd el az alábbi beszélgetés előzményeit, "
                "és fogalmazd át a felhasználó legújabb kérdését egyetlen, önmagában is érthető, "
                "teljes magyar mondattá. Pótold ki a hiányzó neveket (pl. géptípusokat) az előzményekből!\n"
                "FONTOS: Ha a felhasználó láthatóan teljesen ÚJ témát kezd, hagyd figyelmen kívül az "
                "előzményeket, és csak az új kérdést írd le tiszta formában!\n\n"
                f"--- ELŐZMÉNYEK ---\n{history_text}\n\n"
                f"--- ÚJ KÉRDÉS ---\n{user_query}\n\n"
                "VÁLASZKÉNT CSAK AZ ÚJRAÍRT KÉRDÉST ÍRD LE, SEMMI MÁST!"
            )

            print("Előzmények elemzése és kérdés értelmezése...")
            # Itt érdemes az llm_service-ben egy kis kontextus-ablakot használni (pl. num_ctx=1024),
            # de a 14B modellt hívjuk!
            search_query = llm_service.generate_chat_response(
                prompt=rewriter_prompt, pdf_context=""
            ).strip()
            print(f"Expanded question for the Modell: {search_query}")
        else:
            # Ha ez a legelső kérdés, nincs mit újraírni
            search_query = user_query
            print(f"Expanded question for the Modell: {search_query}")

        # router logic
        router_prompt = (
            "Döntsd el a következő kérdésről, hogy egy ÁTFOGÓ (listázó, összesítő, "
            "több dolgot firtató) kérdés-e, vagy egy RÉSZLETES (konkrét lépésre, "
            "adatra, egyetlen hibaelhárítási folyamatra vonatkozó) kérdés.\n\n"
            f"Kérdés: {search_query}\n\n"
            "Csak egyetlen szót válaszolj! Ha átfogó, írd ezt: SUMMARY. Ha részletes, írd ezt: CHUNK."
        )

        routing_decision = (
            llm_service.generate_chat_response(prompt=router_prompt, pdf_context="")
            .strip()
            .upper()
        )

        if "SUMMARY" in routing_decision:
            print("Summary question detected...")
            # A 'filter' paraméterrel megmondjuk a LangChain-nek, hogy csak az összefoglalókat hozza!
            docs = vector_client.db.similarity_search(
                search_query, k=10, filter={"type": "summary"}
            )
        else:
            print("Chunk question detected...")
            # Itt csak a részletes szerelési/üzemeltetési leírásokat húzzuk be
            docs = vector_client.db.similarity_search(
                search_query, k=10, filter={"type": "chunk"}
            )

        # docs = vector_client.db.similarity_search(user_query, k=10)

        # 2. Összeállítjuk a szöveges kontextust a forrásokkal
        context_parts = []
        used_sources = set()

        for i, d in enumerate(docs):
            source_path = d.metadata.get("source", "Ismeretlen dokumentum")
            file_name = os.path.basename(
                source_path
            )  # Csak a fájlnév kell, a hosszú elérési út nem

            # 1. Beletesszük a fájlnevet a halmazba (a forráslistához a végén)
            used_sources.add(file_name)

            # 2. Beégetjük a fájlnevet az LLM-nek szánt "puskába" is
            context_parts.append(
                f"--- {i+1}. PART | SOURCE: {file_name} ---\n{d.page_content}"
            )

        pdf_context = "\n\n".join(context_parts)

        """
        for d in docs:
            source_file = d.metadata.get("source", "Unknown document")
            context_parts.append(f"[{source_file}]: {d.page_content}")

        pdf_context = "\n\n".join(context_parts)
        """

        answer = llm_service.generate_chat_response(search_query, pdf_context)
        final_answer = answer + "\n\n---\n**Used source documents:**\n"

        for source in used_sources:
            final_answer += f"- {source}\n"

        self.chat_history.append(f"User: {search_query}")
        self.chat_history.append(
            f"System: {answer}"
        )  # A nyers választ mentjük, a forráslista nélkül

        # hogy ne teljen be a RAM
        if len(self.chat_history) > 10:
            self.chat_history = self.chat_history[-10:]

        return final_answer

    """
    def search_and_chat(self, user_query: str):
        print(f"Processing query: {user_query}")
        
        # ==========================================
        # STEP 1: HISTORY & QUERY REWRITE
        # ==========================================
        if len(self.chat_history) > 0:
            history_text = "\n".join(self.chat_history[-4:])
            
            rewriter_prompt = (
                "Te egy intelligens asszisztens vagy. Olvasd el az alábbi beszélgetés előzményeit, "
                "és fogalmazd át a felhasználó legújabb kérdését egyetlen, önmagában is érthető, "
                "teljes magyar mondattá. Pótold ki a hiányzó neveket (pl. géptípusokat) az előzményekből!\n"
                "FONTOS: Ha a felhasználó láthatóan teljesen ÚJ témát kezd, hagyd figyelmen kívül az "
                "előzményeket, és csak az új kérdést írd le tiszta formában!\n\n"
                f"--- ELŐZMÉNYEK ---\n{history_text}\n\n"
                f"--- ÚJ KÉRDÉS ---\n{user_query}\n\n"
                "VÁLASZKÉNT CSAK AZ ÚJRAÍRT KÉRDÉST ÍRD LE, SEMMI MÁST!"
            )
            
            print("Analyzing chat history and interpreting the question...")
            # Generating search query based on context. 
            # Note: A smaller context window (e.g., num_ctx=1024) is recommended for this fast call.
            search_query = llm_service.generate_pdf_chat_response(prompt=rewriter_prompt, pdf_context="").strip()
            print(f"Expanded question for the Model: {search_query}")
        else:
            # If this is the first question, there's no history to rewrite
            search_query = user_query
            print(f"Expanded question for the Model: {search_query}")
        
        # ==========================================
        # STEP 2: ROUTER LOGIC
        # ==========================================
        router_prompt = (
            "Döntsd el a következő kérdésről, hogy egy ÁTFOGÓ (listázó, összesítő, "
            "több dolgot firtató) kérdés-e, vagy egy RÉSZLETES (konkrét lépésre, "
            "adatra, egyetlen hibaelhárítási folyamatra vonatkozó) kérdés.\n\n"
            f"Kérdés: {search_query}\n\n"
            "Csak egyetlen szót válaszolj! Ha átfogó, írd ezt: SUMMARY. Ha részletes, írd ezt: CHUNK."
        )
        
        routing_decision = llm_service.generate_pdf_chat_response(prompt=router_prompt, pdf_context="").strip().upper()
        
        # ==========================================
        # STEP 3: TARGETED SEARCH
        # ==========================================
        if "SUMMARY" in routing_decision:
            print("Summary question detected. Searching in summary chunks...")
            # Using the 'filter' parameter to exclusively fetch parent summaries
            docs = vector_client.db.similarity_search(search_query, k=10, filter={"type": "summary"})
        else:
            print("Detailed question detected. Searching in standard chunks...")
            # Fetching specific detailed chunks
            docs = vector_client.db.similarity_search(search_query, k=10, filter={"type": "chunk"})
        
        # ==========================================
        # STEP 4: ASSEMBLE CONTEXT & EXTRACT SOURCES
        # ==========================================
        context_parts = []
        used_sources = set()

        for i, d in enumerate(docs):
            source_path = d.metadata.get("source", "Unknown document")
            file_name = os.path.basename(source_path) # We only need the filename, not the full path
            
            # Add filename to the set for the final list
            used_sources.add(file_name)
            
            # Inject the filename into the LLM context snippet
            context_parts.append(f"--- PART {i+1} | SOURCE: {file_name} ---\n{d.page_content}")

        pdf_context = "\n\n".join(context_parts)
        
        # ==========================================
        # STEP 5: GENERATE FINAL ANSWER WITH INLINE CITATIONS
        # ==========================================
        print("Generating final answer based on retrieved documents...")
        
        # Enforcing inline citations in the final query
        enforced_query = (
            f"Kérdés: {search_query}\n\n"
            "SZIGORÚ SZABÁLY: A válaszodban minden tényállítás vagy bekezdés végén kötelezően "
            "tüntesd fel szögletes zárójelben a forrásfájl nevét, amiből az információt vetted! "
            "(Például: 'A szivattyút havonta kell zsírozni [karbantartas.pdf].')"
        )
        
        answer = llm_service.generate_pdf_chat_response(enforced_query, pdf_context)
        
        # Append the list of verified sources at the bottom
        final_answer = answer + "\n\n---\n**Used source documents:**\n"
        for source in used_sources:
            final_answer += f"- {source}\n"
        
        # ==========================================
        # STEP 6: UPDATE CHAT HISTORY
        # ==========================================
        self.chat_history.append(f"User: {user_query}")
        self.chat_history.append(f"System: {answer}") # Save the raw answer without the appended source list
        
        # Keep only the last 10 messages (5 turns) to prevent RAM overflow
        if len(self.chat_history) > 10:
            self.chat_history = self.chat_history[-10:]
            
        return final_answer
    """

    """
    1 step searching
    def search_and_chat(self, user_query: str):
            print(f"Processing query: {user_query}")
            
            # ==========================================
            # STEP 1: HISTORY & QUERY REWRITE
            # ==========================================
            if len(self.chat_history) > 0:
                history_text = "\n".join(self.chat_history[-4:])
                
                rewriter_prompt = (
                    "Te egy keresési asszisztens vagy. A feladatod: olvasd el a beszélgetés előzményeit, "
                    "majd fogalmazd át a felhasználó LEGÚJABB kérdését egyetlen, önmagában is érthető keresőkérdéssé. "
                    "Pótold a hiányzó neveket (pl. géptípusokat) az előzményekből!\n\n"
                    "SZIGORÚ SZABÁLYOK:\n"
                    "1. NE válaszolj a kérdésre!\n"
                    "2. NE írj állításokat vagy szabályokat, csakis egy kérdést vagy rövid keresőkifejezést!\n"
                    "3. Ha a felhasználó teljesen új témát kezd, hagyd figyelmen kívül az előzményeket!\n\n"
                    "PÉLDÁK:\n"
                    "Előzmény: User: Mennyi az R2-es cső nyomása? | System: Az R2-es cső nyomása 5 bar.\n"
                    "Új kérdés: És hogyan kell cserélni?\n"
                    "Eredmény: R2-es cső cseréjének menete\n"
                    "---\n"
                    "Előzmény: User: Mik a biztonsági követelmények a motor cseréjénél? | System: Munkavédelmi sisak kell.\n"
                    "Új kérdés: És mik a lépései?\n"
                    "Eredmény: Motor cseréjének lépései\n"
                    "---\n\n"
                    f"--- ELŐZMÉNYEK ---\n{history_text}\n\n"
                    f"--- ÚJ KÉRDÉS ---\n{user_query}\n\n"
                    "Eredmény:"
                )
                
                print("Analyzing chat history and interpreting the question...")
                raw_search_query = llm_service.generate_clean_response(prompt=rewriter_prompt, system_prompt="Te egy adatelemző asszisztens vagy. Csak a kért szöveget adod vissza, minden egyéb kommentár nélkül."
                                                                       ).strip()
                if ":" in raw_search_query and len(raw_search_query.split(":")[0]) < 30:
                    search_query = raw_search_query.split(":", 1)[-1].strip()
                else:
                    search_query = raw_search_query
                    search_query = search_query.strip("'\"")
                print(f"Expanded question for the Model: {search_query}")
            
            else:
                search_query = user_query
                print(f"Expanded question for the Model: {search_query}")
                
            # ==========================================
            # STEP 2: PARALLEL SEARCH (Summaries + Detailed Chunks)
            # ==========================================
            print("Running parallel search in documents...")
            
            # 1. Search only among summaries (Big picture / Comparison)
            summary_docs = vector_client.db.similarity_search(
                search_query, 
                k=2, 
                filter={"type": "summary"}
            )
            
            chunk_docs = []
            
            # 2. Search among detailed chunks (chunk and table_chunk) for specific facts
            # Újra megnézzük a kódokat a (már esetleg átírt) search_query-ben is
            current_potential_codes = re.findall(r'\b[A-Za-z0-9]+[-.][A-Za-z0-9]+\b', search_query)
            
            if current_potential_codes:
                code = current_potential_codes[0]
                print(f"Applying exact string matching for code: {code}")
                
                exact_match_docs = vector_client.db.similarity_search(
                    search_query,
                    k=6,
                    filter={"type": {"$in": ["chunk", "table_chunk"]}},
                    # Rákényszerítjük a ChromaDB-t, hogy kis- és nagybetűvel is keresse a kódot!
                    where_document={
                        "$or": [
                            {"$contains": code},
                            {"$contains": code.upper()},
                            {"$contains": code.lower()}
                        ]
                    }
                )
                chunk_docs.extend(exact_match_docs)

            # Ha nincs kód a kérdésben, vagy a kódos keresés nem hozott elég találatot:
            if len(chunk_docs) < 6:
                semantic_docs = vector_client.db.similarity_search(
                    search_query, 
                    k=6 - len(chunk_docs), 
                    filter={"type": {"$in": ["chunk", "table_chunk"]}}
                )
                chunk_docs.extend(semantic_docs)

            # ==========================================
            # STEP 3: ASSEMBLE CONTEXT & EXTRACT SOURCES
            # ==========================================
            context_parts = []
            used_sources = set()

            # --- ADD SUMMARIES TO CONTEXT ---
            if summary_docs:
                context_parts.append("=== COMPREHENSIVE DOCUMENT INFO (For Comparison) ===")
                for i, d in enumerate(summary_docs):
                    source_path = d.metadata.get("source", "Unknown file")
                    file_name = os.path.basename(source_path)
                    used_sources.add(file_name)
                    context_parts.append(f"[DOCUMENT SUMMARY | SOURCE: {file_name}]\n{d.page_content}\n")

            # --- ADD DETAILED CHUNKS TO CONTEXT ---
            if chunk_docs:
                context_parts.append("=== DETAILED EXCERPTS (For Specific Data) ===")
                for i, d in enumerate(chunk_docs):
                    source_path = d.metadata.get("source", "Unknown file")
                    file_name = os.path.basename(source_path)
                    used_sources.add(file_name)
                    context_parts.append(f"[DETAIL | SOURCE: {file_name}]\n{d.page_content}\n")

            pdf_context = "\n".join(context_parts)
            
            # ==========================================
            # STEP 4: GENERATE FINAL ANSWER WITH INLINE CITATIONS
            # ==========================================
            print("Generating final answer based on retrieved documents...")
            
            enforced_query = (
                f"Kérdés: {search_query}\n\n"
                "SZIGORÚ SZABÁLY: A válaszodban minden tényállítás vagy bekezdés végén kötelezően "
                "tüntesd fel szögletes zárójelben a forrásfájl nevét, amiből az információt vetted! "
                "(Például: 'A szivattyút havonta kell zsírozni [karbantartas.pdf].')"
            )
            
            answer = llm_service.generate_pdf_chat_response(enforced_query, pdf_context, num_ctx=16384)
            
            # ==========================================
            # STEP 5: APPEND SOURCE LIST
            # ==========================================
            final_answer = answer + "\n\n---\n**Used source documents:**\n"
            for source in used_sources:
                final_answer += f"- {source}\n"
            
            # ==========================================
            # STEP 6: UPDATE CHAT HISTORY
            # ==========================================
            self.chat_history.append(f"User: {user_query}")
            self.chat_history.append(f"System: {answer}")
            
            if len(self.chat_history) > 10:
                self.chat_history = self.chat_history[-10:]
                
            return final_answer
    
    """
    def _extract_code_variants(self, text: str) -> list[str]:
        """Kódjelöltek a kérdésből; kötőjeles magyar toldalék levágásával is."""
        codes = re.findall(r"\b[A-Za-z0-9]+[-.][A-Za-z0-9]+\b", text)
        variants = []
        for code in codes:
            variants.append(code)
            # "R2-es" -> "R2": rövid, kisbetűs utótag valószínűleg toldalék
            stem, sep, suffix = code.rpartition("-")
            if sep and suffix.islower() and len(suffix) <= 3 and stem:
                variants.append(stem)
        return variants
    
    # ==========================================
    # STEP 1: HISTORY & QUERY REWRITE
    # ==========================================
    def _rewrite_query(self, user_query: str) -> str:
        """Átfogalmazza a kérdést az előzmények alapján, ha szükséges."""
        if len(self.chat_history) > 0:
            history_text = "\n".join(self.chat_history[-4:])
            rewriter_prompt = (
                "Te egy intelligens asszisztens vagy. Olvasd el az alábbi beszélgetés előzményeit, "
                "és fogalmazd át a felhasználó legújabb kérdését egyetlen, önmagában is érthető, "
                "teljes magyar mondattá. Pótold ki a hiányzó neveket (pl. géptípusokat) az előzményekből!\n"
                "FONTOS: Ha a felhasználó láthatóan teljesen ÚJ témát kezd, hagyd figyelmen kívül az "
                "előzményeket, és csak az új kérdést írd le tiszta formában!\n\n"
                f"--- ELŐZMÉNYEK ---\n{history_text}\n\n"
                f"--- ÚJ KÉRDÉS ---\n{user_query}\n\n"
                "VÁLASZKÉNT CSAK AZ ÚJRAÍRT KÉRDÉST ÍRD LE, SEMMI MÁST!"
            )

            print("Analyzing chat history and interpreting the question...")
            raw_search_query = llm_service.generate_clean_response(
                prompt=rewriter_prompt,
                system_prompt="Te egy adatelemző asszisztens vagy. Csak a kért szöveget adod vissza, minden egyéb kommentár nélkül.",
            ).strip()

            if ":" in raw_search_query and len(raw_search_query.split(":")[0]) < 30:
                search_query = raw_search_query.split(":", 1)[-1].strip()
            else:
                search_query = raw_search_query

            search_query = search_query.strip("'\"")
            print(f"Expanded question for the Model: {search_query}")
            return search_query
        else:
            print(f"Expanded question for the Model: {user_query}")
            return user_query

    def _retrieve_documents(self, search_query: str) -> tuple[list, list]:
        """Két fázisú hibrid keresés (Semantic + BM25).
        A relevant_sources CSAK rangsorolásra szolgál, NEM kizárásra."""
        print("Running hybrid (Semantic + BM25) search...")
        CHUNK_LIMIT = 6

        # --- BM25: EGYETLEN hívás, ebből szűrünk summary-t és chunkot is ---
        # (a k=20 az _init_bm25-ben van beállítva, itt már nem írjuk át!)
        bm25_raw = (
            vector_client.bm25_retriever.invoke(search_query)
            if vector_client.bm25_retriever
            else []
        )

        # --- 1. FÁZIS: SUMMARY KERESÉS ---
        semantic_summaries = vector_client.db.similarity_search(
            search_query, k=4, filter={"type": "summary"}
        )
        bm25_summaries = [
            d for d in bm25_raw if d.metadata.get("type") == "summary"
        ][:3]

        # Summary dedup forrás szerint (változatlan)
        summary_docs = []
        seen_summary_sources = set()
        for d in semantic_summaries + bm25_summaries:
            src = d.metadata.get("source")
            if src not in seen_summary_sources:
                summary_docs.append(d)
                seen_summary_sources.add(src)

        relevant_sources = [
            d.metadata.get("source") for d in summary_docs if d.metadata.get("source")
        ][:5]
        print(f"Releváns fájlok (rangsoroláshoz): {relevant_sources}")

        # --- 2. FÁZIS: CHUNK KERESÉS (HIBRID) ---
        chunk_filter = {"type": {"$in": ["chunk", "table_chunk"]}}

        # 2/a. Exact match kódokra – toldalékolt változatot is próbáljuk
        exact_docs = []
        for code in self._extract_code_variants(search_query):
            exact_docs = vector_client.db.similarity_search(
                search_query,
                k=3,
                filter=chunk_filter,
                where_document={
                    "$or": [
                        {"$contains": code},
                        {"$contains": code.upper()},
                        {"$contains": code.lower()},
                    ]
                },
            )
            if exact_docs:
                break  # az első változat, ami találatot ad, nyer

        # 2/b. Szemantikus chunkok
        semantic_chunks = vector_client.db.similarity_search(
            search_query, k=8, filter=chunk_filter
        )

        # 2/c. BM25 chunkok – a releváns forrásokat előre rangsoroljuk
        bm25_chunks = [
            d for d in bm25_raw
            if d.metadata.get("type") in ["chunk", "table_chunk"]
        ]
        bm25_chunks = (
            [d for d in bm25_chunks if d.metadata.get("source") in relevant_sources]
            + [d for d in bm25_chunks if d.metadata.get("source") not in relevant_sources]
        )

        # --- ÖSSZEFÉSÜLÉS: exact garantált, utána felváltva semantic/BM25 ---
        merged = list(exact_docs)
        for sem, bm in zip_longest(semantic_chunks, bm25_chunks):
            if sem is not None:
                merged.append(sem)
            if bm is not None:
                merged.append(bm)

        # Duplikációk kiszűrése (sorrend megtartásával), majd limit
        unique_chunks = []
        seen_content = set()
        for d in merged:
            if d.page_content not in seen_content:
                unique_chunks.append(d)
                seen_content.add(d.page_content)

        return summary_docs, unique_chunks[:CHUNK_LIMIT]

    # ==========================================
    # STEP 3: ASSEMBLE CONTEXT & EXTRACT SOURCES
    # ==========================================
    def _build_context(self, summary_docs: list, chunk_docs: list) -> tuple[str, set]:
        """Összeállítja a promptba kerülő kontextust és a használt források listáját."""
        context_parts = []
        used_sources = set()

        if summary_docs:
            context_parts.append("=== COMPREHENSIVE DOCUMENT INFO (For Comparison) ===")
            for d in summary_docs:
                source_path = d.metadata.get("source", "Unknown file")
                file_name = os.path.basename(source_path)
                used_sources.add(file_name)
                context_parts.append(
                    f"[DOCUMENT SUMMARY | SOURCE: {file_name}]\n{d.page_content}\n"
                )

        if chunk_docs:
            context_parts.append("=== DETAILED EXCERPTS (For Specific Data) ===")
            for d in chunk_docs:
                source_path = d.metadata.get("source", "Unknown file")
                file_name = os.path.basename(source_path)
                used_sources.add(file_name)
                context_parts.append(
                    f"[DETAIL | SOURCE: {file_name}]\n{d.page_content}\n"
                )

        return "\n".join(context_parts), used_sources

    # ==========================================
    # STEP 4: GENERATE FINAL ANSWER WITH INLINE CITATIONS
    # ==========================================
    def _generate_final_answer(
        self, search_query: str, pdf_context: str, used_sources: set
    ) -> tuple[str, str]:
        print("Generating final answer based on retrieved documents...")

        enforced_query = (
            f"KÉRDÉS: {search_query}\n\n"
            "FELADAT: Válaszolj a felhasználó kérdésére magyarul, KIZÁRÓLAG a fenti "
            "kontextus dokumentumok alapján! Ha a kontextusban benne van a válasz, "
            "írd le részletesen. Ha a kontextusból nem derül ki a válasz, egyszerűen "
            "írd le, hogy 'A megadott dokumentumok alapján nem tudom megválaszolni'."
            "A lépéseket a dokumentumban szereplő szöveggel, szó szerint idézd; ne fogalmazd át, ne vond össze és ne egészítsd ki saját szavakkal."
        )

        print(f"[DEBUG] pdf_context hossz: {len(pdf_context)} karakter")
        print(f"[DEBUG] chunk-ok száma: {pdf_context.count('[DETAIL')}")

        # A teljes kontextus kiírása fájlba, hogy meg tudd nézni, mit kapott a modell

        os.makedirs("debug", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_path = f"debug/context_{timestamp}.txt"

        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(f"=== KÉRDÉS (search_query) ===\n{search_query}\n\n")
            f.write(f"=== ENFORCED QUERY ===\n{enforced_query}\n\n")
            f.write(f"=== PDF_CONTEXT ({len(pdf_context)} kar.) ===\n{pdf_context}\n")

        print(f"[DEBUG] Teljes kontextus kiírva: {debug_path}")
        
        raw_answer = llm_service.generate_chat_response(
            enforced_query, pdf_context, chat_history=self.chat_history, num_ctx=16384
        )

        display_answer = raw_answer.strip()

        final_answer = (
            display_answer + "\n\n---\n**Felhasznált forrásdokumentumok:**\n"
        )
        for source in used_sources:
            final_answer += f"- {source}\n"
        
        return display_answer, final_answer
    
    
    # ==========================================
    # STEP 5: UPDATE CHAT HISTORY
    # ==========================================
    def _update_history(self, user_query: str, system_answer: str):
        """Frissíti a beszélgetés előzményeit és levágja a régebbieket."""
        self.chat_history.append(f"User: {user_query}")
        self.chat_history.append(f"System: {system_answer}")

        if len(self.chat_history) > 10:
            self.chat_history = self.chat_history[-10:]

    def search_and_chat(self, user_query: str):

        print(f"Processing query: {user_query}")

        # ==========================================
        # STEP 1: HISTORY & QUERY REWRITE
        # ==========================================
        search_query = self._rewrite_query(user_query)

        # ==========================================
        # STEP 2: KÉTLÉPCSŐS KERESÉS
        # ==========================================
        print("Running hybrid (Semantic + BM25) search...")
        summary_docs, chunk_docs = self._retrieve_documents(search_query)

        # ==========================================
        # STEP 3: ASSEMBLE CONTEXT & EXTRACT SOURCES
        # ==========================================
        pdf_context, used_sources = self._build_context(summary_docs, chunk_docs)

        # ==========================================
        # STEP 4: GENERATE FINAL ANSWER WITH INLINE CITATIONS
        # ==========================================
        raw_answer, final_answer = self._generate_final_answer(
            search_query, pdf_context, used_sources
        )

        # ==========================================
        # STEP 5: UPDATE CHAT HISTORY
        # ==========================================
        self._update_history(user_query, raw_answer)

        return final_answer


rag_service = RAGService()
