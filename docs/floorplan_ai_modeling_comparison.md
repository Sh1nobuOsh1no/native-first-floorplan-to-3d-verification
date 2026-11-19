# 平面图 → AI 建模效果对比

## 真实图纸 4702：输入、自动解析、标注辅助白膜

| 原始完整平面图 | CPU 自动解析候选 | 官方人工 SVG 标注辅助的 Blender 白膜 |
| --- | --- | --- |
| ![4702 原图](../fixtures/real_floorplans/4702/F1_scaled.png) | ![4702 OpenCV 解析叠图](../evidence/cpu/real_floorplans/4702_F1_scaled_6a267a93/parser/parser_overlay.png) | ![4702 白膜视角](../evidence/cpu/real_floorplans/4702_F1_scaled_6a267a93/render_A/rgb/auto_02_space_02_4.png) |
| 官方真实图纸 | OpenCV 墙线 / 房间候选；**未识别可信门洞** | 统一建筑白膜；**使用人工 SVG 标注，不是 AI 自动建模结果** |

| 全建筑布局与相机 | 门洞两侧白膜 RGB | 跨门结构对照 |
| --- | --- | --- |
| ![布局与相机](../evidence/cpu/real_floorplans/4702_F1_scaled_6a267a93/layout_camera_map.png) | ![13 视角白膜 RGB](../evidence/cpu/real_floorplans/4702_F1_scaled_6a267a93/render_A/contact_sheet.png) | ![跨门结构检查](../evidence/cpu/real_floorplans/4702_F1_scaled_6a267a93/cross_door_structure.png) |
| 6 空间 / 10 墙 / 5 室内门 | Blender CPU，13 视角 | 穿门射线 5/5；深度 + ID 重投影 4/5 |

| RGB | Depth | Object ID |
| --- | --- | --- |
| ![同一门洞 RGB](../evidence/cpu/real_floorplans/4702_F1_scaled_6a267a93/render_A/rgb/door_opening_006_Door_space_00.png) | ![同一门洞 Depth](../evidence/cpu/real_floorplans/4702_F1_scaled_6a267a93/render_A/depth/door_opening_006_Door_space_00.png) | ![同一门洞 ID](../evidence/cpu/real_floorplans/4702_F1_scaled_6a267a93/render_A/object_id/door_opening_006_Door_space_00.png) |

## 另外四张真实图纸：原图与自动解析效果

| 图纸 | 原图 | CPU 解析叠图 | 白膜 |
| --- | --- | --- | --- |
| 2055 | ![2055 原图](../fixtures/real_floorplans/2055/F1_scaled.png) | ![2055 解析](../evidence/cpu/real_floorplans/2055_F1_scaled_d55db949/parser/parser_overlay.png) | 未生成可信 Metric Scene |
| 4790 | ![4790 原图](../fixtures/real_floorplans/4790/F1_scaled.png) | ![4790 解析](../evidence/cpu/real_floorplans/4790_F1_scaled_2c7495d5/parser/parser_overlay.png) | 未生成可信 Metric Scene |
| 8741 | ![8741 原图](../fixtures/real_floorplans/8741/F1_scaled.png) | ![8741 解析](../evidence/cpu/real_floorplans/8741_F1_scaled_0935e544/parser/parser_overlay.png) | 未生成可信 Metric Scene |
| 9557 | ![9557 原图](../fixtures/real_floorplans/9557/F1_scaled.png) | ![9557 解析](../evidence/cpu/real_floorplans/9557_F1_scaled_f13ce9ed/parser/parser_overlay.png) | 未生成可信 Metric Scene |

## 效果与验收状态

| 项目 | 实测结果 | 证据 |
| --- | --- | --- |
| 5 张真实图纸的自动房间框 | 17/36 匹配 | [批量评估](../evidence/cpu/real_floorplans/parser_only_batch_summary.json) |
| 5 张真实图纸的自动门洞 | 0/42 | [批量评估](../evidence/cpu/real_floorplans/parser_only_batch_summary.json) |
| 真实图纸 → 自动 Metric Scene → 白膜 | 0/5 完整通过 | [批量结果](../evidence/cpu/real_floorplans/batch_summary.json) |
| 4702 人工标注辅助 → Blender 白膜 | 已运行；统一 [GLB](../evidence/cpu/real_floorplans/4702_F1_scaled_6a267a93/render_A/building_unified.glb) | [Metric Scene](../evidence/cpu/real_floorplans/4702_F1_scaled_6a267a93/metric_scene.json) · [13 视角](../evidence/cpu/real_floorplans/4702_F1_scaled_6a267a93/render_A/contact_sheet.png) |
| 4702 → GenRecon Sage_gt CPU Reader | 18/20 Chunk 有接受相机；2 fallback | [Reader 报告](../evidence/cpu/real_floorplans/4702_F1_scaled_6a267a93/native_A_report.json) |
| GenRecon 网络生成的真实感 mesh / PBR | **未运行；无效果图** | [GPU 实验单](gpu_experiments.md) |

## 合成建筑控制组（非真实图纸）

| 结构白膜 A | 粗家具白膜 B | 跨门重投影 |
| --- | --- | --- |
| ![合成 A](../evidence/cpu/render_A/contact_sheet.png) | ![合成 B](../evidence/cpu/render_B/contact_sheet.png) | ![合成跨门](../evidence/cpu/cross_door_check.png) |
| 20 视角；30/30 Chunk；0 fallback | 同相机；30/30 Chunk；0 fallback | 4/4 门通过；**仅验证 Blender 场景** |
