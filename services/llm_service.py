from ollama import Client
from config.settings import settings
from src.utils.document_processor import get_pdf_text
import yaml
import time


class LLMService:
    def __init__(self):
        # Ollama client; host and model come from config/settings.py (.env)
        self.client = Client(host=settings.ollama_host)
        self.model = settings.ollama_model
        with open("config/prompt.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        self.system_template = config["prompt_settings"]["system_instruction"]
        
        
    def generate_chat_response_old(self, prompt: str, pdf_context: str) -> str:
        """
        Sends a user prompt to the LLM and returns the generated text response.
        """
        response = self.client.chat(
            model=self.model, messages=[{"role": "user", "content": prompt}]
        )

        # Extract and return the actual text content from the JSON response
        return response["message"]["content"]

    def generate_demo_pdf_chat_response(
        self, prompt: str, pdf_context: str = ""
    ) -> str:
        """
        Sends a user prompt and the extracted PDF context to the LLM
        and returns the generated text response.
        """
        pdf_context = get_pdf_text(
            [
                "pdfs/Approved.MWI-63176.1.20251205.64428.File1.pdf",
                "pdfs/Approved.MWI-63906.0.20250929.63906.File1.pdf",
            ]
        )
        # 1. Assemble the system instruction, embedding the PDF text
        system_instruction = (
            "You are an intelligent assistant. Answer the user's question based "
            "on the content of the following documents. If the answer is "
            "not in the documents, indicate that you do not know.\n\n"
            f"DOCUMENT TEXT\n{pdf_context}\n"
        )

        # 2. Send the call to Ollama with the modified settings
        response = self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            # 3. EXTENDED CONTEXT! Without this, it would throw an error or forget with long PDFs.
            # 32768 tokens is enough for Qwen2.5 to process several pages.
            options={"num_ctx": 32768},
        )

        # Extract and return the actual text content from the JSON response
        return response["message"]["content"]

    def generate_chat_response(
        self, prompt: str, pdf_context: str, chat_history: list = None, num_ctx=8192
    ) -> str:

        system_instruction = self.system_template.format(pdf_context=pdf_context)

        messages = [{"role": "system", "content": system_instruction}]

        if chat_history:
            for entry in chat_history:
                if entry.startswith("User: "):
                    messages.append({"role": "user", "content": entry[len("User: "):]})
                elif entry.startswith("System: "):
                    messages.append({"role": "assistant", "content": entry[len("System: "):]})

        # Az aktuális kérdés előzmények nélkül is mindig bekerül
        messages.append({"role": "user", "content": prompt})

        start_time = time.time()

        response = self.client.chat(
            model=self.model,
            messages=messages,
            options={
                "num_ctx": num_ctx,
                "num_predict": 4096,
                "num_gpu": 99,
                "temperature": 0.1
            },
        )

        # STOP TIMER
        elapsed_seconds = time.time() - start_time

        input_tokens = response.get("prompt_eval_count", 0)
        output_tokens = response.get("eval_count", 0)
        total_tokens = input_tokens + output_tokens

        print(f"   Input: {input_tokens} token")
        print(f"   Output:     {output_tokens} token")
        print(f"   All:          {total_tokens} token")
        print(f"   Time:          {elapsed_seconds:.2f} second")

        return response["message"]["content"]

    def generate_clean_response(
        self, prompt: str, system_prompt: str = "You are a precise assistant."
    ) -> str:
        """
        Clean LLM call without RAG context and YAML configurations.
        Specifically for Query Rewriting and other meta-tasks.
        """
        # No YAML loading, no pdf_context!
        response = self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            options={
                "num_ctx": 4096,  # More than enough for query rewriting
                "temperature": 0.0,  # 0.0 -> Do not be creative, just execute the command
                "num_predict": 2000,  # We do not expect a long response
                "num_gpu": 99,
            },
        )

        return response["message"]["content"]


# Instantiate the service so routers can import and use it directly
llm_service = LLMService()
