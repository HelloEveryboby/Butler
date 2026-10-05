# vendor/lang — OCR 语言包（可选组件）

这里存放 tesseract 的 `*.traineddata.gz` 训练数据，供**图片翻译 / 截图翻译**使用。

## 为什么要单独下载？

训练数据体积较大（`eng` ≈ 4 MB，`chi_sim` ≈ 2 MB），不适合直接提交进 Git 仓库。
构建时由 `webpack.config.ts` 的 `CopyWebpackPlugin` 原样拷贝到 `dist/vendor/lang/`。

## 下载

```bash
npm run fetch:ocr-lang              # 默认下载 eng + chi_sim
npm run fetch:ocr-lang -- jpn kor   # 下载其他语言
```

## 离线说明

- 不下载语言包时：网页翻译 / PDF 翻译 / 文本翻译 **不受影响**，完全离线可用。
- 图片翻译会提示"缺少 OCR 语言包"，运行上面的命令即可补上。

语言包来源：[tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast)（Apache 2.0）。
