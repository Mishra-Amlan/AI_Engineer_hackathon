---
id: SLM_Comprehensive_Guide#0014
domain: slm
risk_tier: 1
version: v1
---
# Step 2: Complete Fine-Tuning Python Script

" ] ) ] return { " text " : texts } dataset = dataset. from _ dict ( { " instruction " : [ " extract batch details. " ], " input " : [ " log : incident report # 442 for lot - 12345. " ], " output " : " { \ " batch \ " : \ " lot - 12345 \ ", \ " status \ " : \ " flagged \ " } " } ) dataset = dataset. map ( formatting _ func, batched = true ) # 4. trainer configuration trainer = sfttrainer ( model = model, tokenizer = tokenizer, train _ dataset = dataset, dataset _ text _ field = " text ", max _ seq _ length = max _ seq _ length, dataset _ num _ proc = 2, packing = false, args = trainingarguments ( per _ device _ train _ batch _ size = 2, gradient _ accumulation _ steps = 4, warmup _ ratio = 0. 05, num _ train _ epochs = 3, learning _ rate = 2e - 4, fp16 = not torch. cuda. is _ bf16 _ supported ( ), bf16 = torch. cuda. is _ bf16 _ supported ( ), logging _ steps = 1, optim = " adamw _ 8bit ", weight _ decay = 0. 01, output _ dir = " outputs ", ), ) trainer _ stats = trainer. train ( ) model. save _ pretrained _ merged ( " model _ lora _ saved ", tokenizer, save _ method = " merged _ 16bit " )

## Related
- [[SLM_Comprehensive_Guide_0013]]
- [[SLM_Comprehensive_Guide_0015]]
