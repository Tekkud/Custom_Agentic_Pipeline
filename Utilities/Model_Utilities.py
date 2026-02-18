from llama_cpp import Llama
from llama_cpp import llama_tokenize
from . import constants as c


def load_model(model_path, n_gpu_layers = -1, n_ctx = None, use_mmap = False, verbose = False, temperature = .7, min_p = 0.0, top_p = .9, top_k = 0, repeat_penalty = 1.15):
    if n_ctx == None:
        n_ctx = c.context_total
    llm = Llama(
        model_path = model_path,
        n_gpu_layers = n_gpu_layers,
        n_ctx = n_ctx,
        use_mmap = use_mmap,
        verbose = verbose,
        temperature = temperature,
        top_p = top_p,
        min_p =  min_p,
        top_k = top_k,
        flash_attn=False,
        repeat_penalty = repeat_penalty
    )
    return llm