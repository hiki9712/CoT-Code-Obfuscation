Flashboom 数据文件格式：

- 3个数据集：smartbugs-collection, big-vul-100, cvefixes-100
  - 每个数据集下包含原始代码（code）
  - 漏洞检测 GroundTruth（explanation）
  - 插入 Flashboom 后的代码（Flashboom）
    - 按（Mixtral，MixtralExpert，Gemma，Phi，CodeLlama）这5个模型归类，这里给出了每个模型上效果top1的Flashboom，例如`smartbugs-collection\Flashboom\CodeLlama\1644-CustomToken.CustomToken` 代表 smartbugs-collection 数据集上，在CodeLlama模型上搜索到的、且在CodeLlama模型上攻击成功率 top1 的代码，其命名格式与 code 目录一致