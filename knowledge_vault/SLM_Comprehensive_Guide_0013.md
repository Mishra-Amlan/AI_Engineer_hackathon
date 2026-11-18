---
id: SLM_Comprehensive_Guide#0013
domain: slm
risk_tier: 1
version: v1
---
# Step 2: Complete Fine-Tuning Python Script

import torch from unsloth import fastlanguagemodel from datasets import dataset from trl import sfttrainer from transformers import trainingarguments max _ seq _ length = 2048 dtype = none # auto - detection load _ in _ 4bit = true # 4 - bit quantization for qlora # 1. load pre - trained base model & tokenizer model, tokenizer = fastlanguagemodel. from _ pretrained ( model _ name = " unsloth / qwen2. 5 - 3b - instruct ", max _ seq _ length = max _ seq _ length, dtype = dtype, load _ in _ 4bit = load _ in _ 4bit, ) # 2. setup qlora target modules model = fastlanguagemodel. get _ peft _ model ( model, r = 64, # lora rank target _ modules = [ " q _ proj ", " k _ proj ", " v _ proj ", " o _ proj ", " gate _ proj ", " up _ proj ", " down _ proj " ], lora _ alpha = 16, lora _ dropout = 0, bias = " none ", use _ gradient _ checkpointing = " unsloth ", random _ state = 3407, ) # 3. prompt template formatting prompt _ style = " " " < | im _ start | > system \ nyou are an enterprise compliance assistant. < | im _ end | > \ n < | im _ start | > user \ n { instruction } \ n { input } < | im _ end | > \ n < | im _ start | > assistant \ n { output } < | im _ end | > " " " def formatting _ func ( examples ) : texts = [ prompt _ style. format ( instruction = i, input = inp, output = o ) + tokenizer. eos _ token for i, inp, o in zip ( examples [ " instruction " ], examples [ " input " ], examples [ " output " ] ) ] return { " text " : texts } dataset = dataset. from _ dict ( { " instruction " : [ " extract batch details. " ], " input " : [ " log : incident report # 442 for lot - 12345. " ], " output " : "

## Related
- [[SLM_Comprehensive_Guide_0012]]
- [[SLM_Comprehensive_Guide_0014]]
