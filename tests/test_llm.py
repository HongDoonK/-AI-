import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig


LLM_MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"


def main():
    print("GPU 사용 가능 여부:", torch.cuda.is_available())

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4"
    )

    tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL_NAME)

    llm = AutoModelForCausalLM.from_pretrained(
        LLM_MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto"
    )

    messages = [
        {
            "role": "system",
            "content": "너는 청년정책 추천을 도와주는 신중한 AI assistant다."
        },
        {
            "role": "user",
            "content": "서울 사는 25살 취준생에게 월세 지원 정책을 안내하는 예시 답변을 짧게 작성해줘."
        }
    ]

    input_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(input_text, return_tensors="pt").to(llm.device)

    outputs = llm.generate(
        **inputs,
        max_new_tokens=500,
        temperature=0.3,
        do_sample=True
    )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)

    print(response)


if __name__ == "__main__":
    main()