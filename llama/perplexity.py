import math


class CalculatePerplexity:
    """Calcula logprobs e perplexidade da resposta gerada.

    Antes exigia acesso direto aos logits de um modelo local (forward pass
    completo via `self.model(sequences).logits`). Agora que a geração é
    feita pela API de Chat Completions da OpenAI, usamos os logprobs que a
    própria API já retorna por token gerado (parâmetro `logprobs=True` em
    `client.chat.completions.create`), sem precisar recomputar nada
    localmente.
    """

    def get_logprobs(self, completion):
        """
        completion -> objeto retornado por client.chat.completions.create(
                          ..., logprobs=True
                      )
        """
        choice = completion.choices[0]
        token_logprobs = choice.logprobs.content if choice.logprobs else []

        pairs = [(t.token, t.logprob) for t in token_logprobs]

        if not pairs:
            return pairs, 0.0, float("inf")

        logprob_values = [lp for _, lp in pairs]
        mean_logprob = sum(logprob_values) / len(logprob_values)
        perplexity = math.exp(-mean_logprob)

        return pairs, mean_logprob, perplexity
