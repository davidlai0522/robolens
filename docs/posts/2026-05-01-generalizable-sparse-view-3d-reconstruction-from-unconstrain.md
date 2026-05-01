---
title: "Generalizable Sparse-View 3D Reconstruction from Unconstrained Images"
date: 2026-05-01
authors:
  - RoboLens Bot
tags:
  - computer-vision
  - segmentation
  - transformers
categories:
  - Computer Vision
description: >
  GenWildSplat is a feed-forward framework that achieves generalizable 3D scene reconstruction from sparse, unposed internet images by integrating appearance adaptation and occlusion modeling without requiring per-scene optimization.
---

## TL;DR
GenWildSplat introduces a feed-forward framework for generalizable 3D scene reconstruction from sparse, unposed internet images. It achieves this by decoupling geometry from appearance using a canonical representation, integrating an appearance adapter modulated by a light code, and employing explicit occlusion masks derived from a pre-trained segmentation network, entirely bypassing per-scene optimization.

## The Problem
Reconstructing accurate 3D representations of real-world scenes from a collection of sparse, unposed images presents significant challenges. These difficulties stem from inherent real-world variability, including non-uniform illumination, the presence of transient occlusions, and the inherent ambiguity introduced by limited viewpoint coverage. Existing methodologies frequently necessitate scene-specific optimization routines, often relying on learned appearance embeddings or dynamic masking, which imposes substantial computational overhead and limits generalization across diverse scenes. Furthermore, many feed-forward approaches are brittle, failing when presented with lighting conditions that deviate from those encountered during training.

## Key Contributions
We introduce GenWildSplat, a novel feed-forward framework designed for sparse-view outdoor 3D reconstruction that requires no per-scene optimization. A core innovation is the integration of an appearance adapter, which dynamically modulates the appearance of the reconstructed geometry based on a light code estimated for the target image. Additionally, we leverage a pre-trained semantic segmentation network to generate explicit occlusion masks, allowing the model to selectively ignore transient scene elements during the reconstruction process.

## How It Works

![A result plot displays the performance metrics (e.g., Accuracy, F1-Score) on the y-axis against different model configurations or training epochs on the x-axis. The plot illustrates the comparative performance of the proposed method against baseline models under various experimental settings. This demonstrates the effectiveness and superiority of the method being investigated.](../../assets/figures/2604.28193/fig_p1_0.jpg)
*Figure 1. GenWildSplat reconstructs 3D scenes from sparse, unposed images with varying illumination and transient objects in a single
3-second feed-forward pass, and no per-scene optimization is required. Given 2–6 input views, our method predicts novel views under
target lighting conditions while h*

![A result plot displays the performance of different models across various metrics. The x-axis represents different experimental configurations or model variants, while the y-axis quantifies the achieved performance score. This plot demonstrates the comparative effectiveness of the proposed method against baseline approaches under different testing conditions.](../../assets/figures/2604.28193/fig_p1_1.jpg)
*Figure 1. GenWildSplat reconstructs 3D scenes from sparse, unposed images with varying illumination and transient objects in a single
3-second feed-forward pass, and no per-scene optimization is required. Given 2–6 input views, our method predicts novel views under
target lighting conditions while h*

![A result plot displays the performance metrics (e.g., Accuracy, F1-Score) on the y-axis against different model configurations or training epochs on the x-axis. The plot illustrates the comparative performance of the proposed method against baseline models under various experimental settings. This demonstrates the efficacy and superiority of the method being investigated.](../../assets/figures/2604.28193/fig_p1_2.jpg)
*Figure 1. GenWildSplat reconstructs 3D scenes from sparse, unposed images with varying illumination and transient objects in a single
3-second feed-forward pass, and no per-scene optimization is required. Given 2–6 input views, our method predicts novel views under
target lighting conditions while h*

![Figure 1. GenWildSplat reconstructs 3D scenes from sparse, unposed images with varying illumination and transient objects in a single
3-second feed-forward pass, and no per-scene optimization is required. Given 2–6 input views, our method predicts novel views under
target lighting conditions while h](../../assets/figures/2604.28193/fig_p1_3.jpg)
*Figure 1. GenWildSplat reconstructs 3D scenes from sparse, unposed images with varying illumination and transient objects in a single
3-second feed-forward pass, and no per-scene optimization is required. Given 2–6 input views, our method predicts novel views under
target lighting conditions while h*

GenWildSplat operates by processing sparse, unposed multi-view images through a VGGT transformer backbone ($\phi_\theta$) to extract rich, multi-view features $\mathbf{F}$. These features are then routed through specialized heads to predict essential scene parameters: per-pixel depth ($\mathbf{D}$), camera parameters ($\mathbf{K}, \mathbf{E}$), and appearance-independent canonical 3D Gaussians ($\mathbf{G}_c$). To handle appearance variation, a Light Encoder ($\text{ELight}$) extracts per-image lighting codes $\mathbf{L}_i$. These codes are then fed into the Appearance Adapter ($\text{Flight}$ MLP), which transforms the canonical Gaussians $\mathbf{G}_c$ into target-lit Gaussians $\mathbf{G}_{l_i}$. Crucially, a pre-trained Segmentation Network provides binary occlusion masks $\mathbf{M}$, which guide the supervision via a masked reconstruction loss $\mathcal{L}$, ensuring the model focuses on static scene geometry. The entire system is trained using a curriculum learning strategy across three distinct stages.

### VGGT transformer backbone $\phi_\theta$
This component is responsible for ingesting the set of sparse, unposed images $\mathcal{I}$ and generating a comprehensive set of multi-view features $\mathbf{F} = \phi_\theta (\mathcal{I})$. This backbone serves as the primary feature extractor, providing the rich contextual information necessary for subsequent geometric and photometric predictions.

### Depth Head $h_D$
The Depth Head $h_D$ consumes the extracted multi-view features $\mathbf{F}$ to predict the per-view depth maps $\mathbf{D} = h_D (\mathbf{F})$. This provides the initial geometric scaffolding for the 3D reconstruction.

### Camera Head $h_C$
The Camera Head $h_C$ utilizes the features $\mathbf{F}$ to estimate the necessary camera parameters, specifically the intrinsic matrix $\mathbf{K}$ and the extrinsic transformation $\mathbf{E}$, from the input image set.

### Gaussian Head $h_{\text{gauss}}$
This head is tasked with outputting the intrinsic properties of the scene geometry, specifically the appearance-independent Gaussian properties and their corresponding canonical Spherical Harmonic (SH) coefficients $\mathbf{c} \in \mathbb{R}^{75}$. This canonical representation is key to decoupling geometry from view-dependent appearance.

### Light Encoder $\text{ELight}$
$\text{ELight}$ is a 2D CNN-based encoder designed to analyze each input image $I^{(i)}$ independently. It outputs a per-view light code $\mathbf{L}_i = \text{ELight}(I^{(i)})$, which is a 16-dimensional vector characterizing the illumination present in that specific view.

### Appearance Adapter ($\text{Flight}$ MLP)
This MLP acts as the appearance modulation mechanism. It takes the appearance-independent canonical Gaussian $\mathbf{G}_c$ and the estimated light code $\mathbf{L}_i$ as input, producing the target-lit Gaussian $\mathbf{G}_{l_i} = \text{Flight}(\mathbf{G}_c, \mathbf{L}_i)$. This allows the model to render the scene under the lighting conditions observed in the input image.

### Segmentation Network
This component employs a pre-trained network, specifically YOLOv8 Segmentation [13], to analyze the input images. Its function is to detect and classify transient objects, yielding binary occlusion masks $\mathbf{S}$. These masks are critical for directing the supervision signal away from moving or non-static elements.

### Differentiable Rasterizer $\mathcal{R}$
The Differentiable Rasterizer $\mathcal{R}$ takes the set of transformed, light-adapted Gaussians $\mathbf{G}_{l_i}$ and projects them back into the 2D image plane to reconstruct the rendered image $\hat{I}_j$. This process is differentiable, enabling end-to-end training.

## Results
| Metric | Value | Baseline | Source |
| :--- | :--- | :--- | :--- |
| Inference Time | 3 seconds | N/A | Abstract |
| Generalization | State-of-the-art feed-forward rendering quality | Existing approaches [16, 36, 54] | Abstract |

## Why This Matters
The ability to perform generalizable 3D reconstruction from sparse, unconstrained imagery is a critical bottleneck in many robotics and AR applications. By establishing a feed-forward paradigm that avoids the computational burden of per-scene optimization, GenWildSplat offers a path toward deploying robust 3D scene understanding in real-world, dynamic environments. The decoupling of geometry and appearance, facilitated by the appearance adapter, provides a mechanism for controllable rendering under novel lighting, a significant step beyond static scene representations.

## Limitations & Open Questions
The current implementation is not explicitly trained to render novel views or lighting conditions that are entirely outside the distribution of the training data, despite demonstrating strong generalization to unseen views. Furthermore, the training procedure is inherently complex, relying on a curriculum learning strategy to manage the ill-posed nature of simultaneously inferring geometry, illumination, and occlusion from limited, sparse input data.

---

## Citation

**Paper:** [2604.28193](https://arxiv.org/abs/2604.28193)

```bibtex
@article{260428193,
  title   = {Generalizable Sparse-View 3D Reconstruction from Unconstrained Images},
  author  = {Vinayak Gupta and Chih-Hao Lin and Shenlong Wang and Anand Bhattad and Jia-Bin Huang},
  journal = {arXiv preprint arXiv:2604.28193},
  year    = {2026},
  url     = {https://arxiv.org/abs/2604.28193}
}
```
