from services.rag_service import rag_service
from data.raw.vector_store import vector_client

from services.rag_service import rag_service
kerdes = "#268 Sorjázó levegőelőkészítő cseréhez milyen gépek és alkatrészek kellenek?"
print(rag_service.search_and_chat(kerdes))