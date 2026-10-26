import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification


class RankContext:

    def __init__(self, model, top_n=6):

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.tokenizer = AutoTokenizer.from_pretrained(model)
        self.model = AutoModelForSequenceClassification.from_pretrained(model)

        self.model.to(self.device)
        self.model.eval()

        self.top_n = top_n


    def call_rank(self, query, documents):

        if not documents:
            # Sem candidatos pra reordenar (ex.: base do RAG ainda vazia, ou
            # a busca não encontrou nada relevante). Chamar o tokenizer com
            # uma lista vazia quebra (IndexError dentro do transformers), e
            # logicamente não há nada a rerankear mesmo.
            return []

        texts = [d.page_content for d in documents]

        pairs = [[query, t] for t in texts]

        inputs = self.tokenizer(
            pairs,
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=512
        ).to(self.device)

        with torch.no_grad():
            scores = self.model(**inputs).logits.squeeze(-1)

        scored_docs = list(zip(scores.cpu().tolist(), documents))

        scored_docs.sort(reverse=True, key=lambda x: x[0])

        ranked = [d for _, d in scored_docs[:self.top_n]]

        print("\n🏆 Reranker ranking:")
        for s, d in scored_docs[:self.top_n]:
            print(f"{s:.4f} | {d.metadata} | [doc_id: {d.id}]")

        return ranked
