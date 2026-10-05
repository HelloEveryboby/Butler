import path from 'path';
import CopyWebpackPlugin from 'copy-webpack-plugin';
import HtmlWebpackPlugin from 'html-webpack-plugin';
import MiniCssExtractPlugin from 'mini-css-extract-plugin';
import type { Configuration } from 'webpack';

/** 把第三方库内置的公网 CDN 回退地址改写为无效占位域（离线承诺） */
function stripCdnFallbacks(content: Buffer): Buffer {
  return Buffer.from(
    content
      .toString('utf8')
      .replace(/https:\/\/(cdnjs|cdn\.jsdelivr|unpkg)\.com\/npm\//g, 'https://butler-local.invalid/npm/')
      .replace(/https:\/\/cdn\.jsdelivr\.net\/npm\//g, 'https://butler-local.invalid/npm/')
  );
}

const config: Configuration = {
  entry: {
    'background/service-worker': './background/service-worker.ts',
    'content/index': './content/index.ts',
    'popup/popup': './popup/popup.ts',
    'options/options': './options/options.ts',
  },
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: '[name].js',
    // 动态 import() 拆出的 chunk（pdfjs-dist / jszip）单独落盘，用到才加载
    chunkFilename: 'chunks/[name].js',
    clean: true,
  },
  module: {
    rules: [
      {
        test: /\.ts$/,
        use: 'ts-loader',
        exclude: /node_modules/,
      },
      {
        test: /\.html$/,
        use: {
          loader: 'html-loader',
          options: {
            // HTML 里只有 <script src="xxx.js">，构建产物就叫 xxx.js，
            // 让 html-loader 不去解析这些 src，避免它把 .js 当作待打包模块。
            sources: false,
          },
        },
      },
    ],
  },
  resolve: {
    extensions: ['.ts', '.js'],
    alias: {
      '@utils': path.resolve(__dirname, 'utils'),
      '@content': path.resolve(__dirname, 'content'),
      '@background': path.resolve(__dirname, 'background'),
    },
  },
  plugins: [
    new CopyWebpackPlugin({
      patterns: [
        { from: 'manifest.json', to: 'manifest.json' },
        { from: 'icons', to: 'icons' },
        // ---- 本地 vendor：彻底摆脱公网 CDN，支持完全离线 ----
        {
          from: 'node_modules/pdfjs-dist/build/pdf.worker.min.mjs',
          to: 'vendor/pdf.worker.min.mjs',
        },
        // JSZip 由 webpack 动态 import 打包进 chunks/，无需单独拷贝
        // tesseract.js 内置的 CDN 默认地址（jsdelivr）在拷贝时改写为无效占位域：
        // 我们始终显式传入本地 workerPath/corePath/langPath，永不触发；
        // 即使将来漏传，也只会本地报错，绝不访问公网。
        {
          from: 'node_modules/tesseract.js/dist/tesseract.min.js',
          to: 'vendor/tesseract.min.js',
          transform: stripCdnFallbacks,
        },
        {
          from: 'node_modules/tesseract.js/dist/worker.min.js',
          to: 'vendor/tesseract.worker.min.js',
          transform: stripCdnFallbacks,
        },
        {
          from: 'node_modules/tesseract.js-core',
          to: 'vendor/tesseract-core',
          globOptions: {
            // 只保留 LSTM 变体（createWorker 用 OEM=1），非 LSTM 的 core 约 15MB 不需要
            ignore: [
              '**/package.json',
              '**/README.md',
              '**/LICENSE',
              '**/index.js',
              '**/*.map',
              '**/tesseract-core.js',
              '**/tesseract-core.wasm',
              '**/tesseract-core.wasm.js',
              '**/tesseract-core-simd.js',
              '**/tesseract-core-simd.wasm',
              '**/tesseract-core-simd.wasm.js',
            ],
          },
        },
        // OCR 语言包（可选，由 npm run fetch:ocr-lang 下载），缺失时不影响构建
        { from: 'vendor/lang', to: 'vendor/lang', noErrorOnMissing: true },
      ],
    }),
    new HtmlWebpackPlugin({
      template: './popup/popup.html',
      filename: 'popup/popup.html',
      chunks: ['popup/popup'],
      // 手动 <script src="popup.js"> 已在模板里，禁止重复注入
      inject: false,
    }),
    new HtmlWebpackPlugin({
      template: './options/options.html',
      filename: 'options/options.html',
      chunks: ['options/options'],
      inject: false,
    }),
    new MiniCssExtractPlugin({
      filename: '[name].css',
    }),
  ],
  optimization: {
    splitChunks: false,
  },
};

export default config;
