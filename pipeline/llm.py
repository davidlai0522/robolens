# pipeline/llm.py
import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

MODEL_ID = "google/gemma-4-E4B-it"

# Reduce CUDA memory fragmentation — harmless if already set
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

# Minimum free VRAM (GiB) required to run bf16 inference without OOM
_MIN_FREE_VRAM_GiB = 6.0


def _auto_quantise() -> bool:
    """Return True if free VRAM is too low for safe bf16 inference."""
    if not torch.cuda.is_available():
        return True  # CPU path — always quantise
    free_bytes = torch.cuda.mem_get_info()[0]
    free_gib = free_bytes / (1024 ** 3)
    if free_gib < _MIN_FREE_VRAM_GiB:
        print(f"  ⚠️  Only {free_gib:.1f} GiB VRAM free — auto-enabling 4-bit quantisation")
        return True
    return False


def load_model(quantise: bool = False):
    """
    Load Gemma 4 E4B locally.

    quantise=False  → bf16, requires ~8 GB VRAM (recommended with GPU)
    quantise=True   → 4-bit via bitsandbytes, requires ~5 GB VRAM / runs on CPU

    If quantise=False but free VRAM is below the threshold, 4-bit is
    enabled automatically to avoid OOM during inference.
    """
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

    if not quantise:
        quantise = _auto_quantise()

    if quantise:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            quantization_config=bnb_config,
            device_map="auto",
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )

    model.eval()
    return tokenizer, model


def ask(
    prompt: str,
    tokenizer,
    model,
    temperature: float = 0.2,
    max_new_tokens: int = 2048,
) -> str:
    """
    Send a single-turn prompt to Gemma 4 and return the response text.
    Uses the model's chat template automatically.
    """
    messages = [{"role": "user", "content": prompt}]
    inputs = tokenizer.apply_chat_template(
        messages,
        return_tensors="pt",
        add_generation_prompt=True,
    )
    # transformers ≥ 5.x returns a BatchEncoding; earlier versions return a plain tensor
    if hasattr(inputs, "input_ids"):
        input_ids = inputs["input_ids"].to(model.device)
    else:
        input_ids = inputs.to(model.device)

    with torch.inference_mode():
        output_ids = model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
        )

    # Decode only the newly generated tokens
    new_tokens = output_ids[0][input_ids.shape[-1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
