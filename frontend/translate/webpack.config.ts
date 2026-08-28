import path from 'path';
import CopyWebpackPlugin from 'copy-webpack-plugin';
import HtmlWebpackPlugin from 'html-webpack-plugin';
import MiniCssExtractPlugin from 'mini-css-extract-plugin';
import type { Configuration } from 'webpack';

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
        use: 'html-loader',
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
      ],
    }),
    new HtmlWebpackPlugin({
      template: './popup/popup.html',
      filename: 'popup/popup.html',
      chunks: ['popup/popup'],
    }),
    new HtmlWebpackPlugin({
      template: './options/options.html',
      filename: 'options/options.html',
      chunks: ['options/options'],
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
