---
document_type: Thesis/Project Proposal
title: "EcoVision: Deep Learning Approaches to Detecting Deforestation in Remote Sensing Data"
subtitle: "Using Google Earth Satellite Imagery (1984–2022)"
focus_areas: [Gazipur, Chittagong Hill Tracts, Sylhet]
authors:
  - name: Sheikh Sulaiman Sony
    id: "2002026"
  - name: Jalal Uddin Mohammad Akbar
    id: "2002050"
supervisor:
  name: Rubel Sheikh
  title: Lecturer
department: Department of Educational Technology and Engineering
institution: University of Frontier Technology, Bangladesh (UFTB)
location: Kaliakair, Gazipur-1750, Bangladesh
date: 2026-04-22
keywords: [Deforestation Detection, Deep Learning, Remote Sensing, Satellite Imagery, U-Net, Change Detection, Bangladesh, Google Earth Engine]
source_file: Project_Thesis_Proposal_Sony_Jalal_Updated.pdf
extraction_note: "Full text extracted verbatim in structure; Figure 1 (workflow diagram) and Figure 2 (Gantt chart) are converted from images into structured text/tables."
---

# EcoVision: Deep Learning Approaches to Detecting Deforestation in Remote Sensing Data

**Thesis/Project Proposal** — Focus Areas: Gazipur | Chittagong Hill Tracts | Sylhet
Using Google Earth Satellite Imagery (1984–2022)

| Field | Value |
|---|---|
| Submitted by | Sheikh Sulaiman Sony (ID: 2002026); Jalal Uddin Mohammad Akbar (ID: 2002050) |
| Department | Educational Technology and Engineering, UFTB |
| Supervised by | Rubel Sheikh, Lecturer, Dept. of ETE, UFTB |
| Institution | University of Frontier Technology, Bangladesh, Kaliakair, Gazipur-1750 |
| Date | April 22, 2026 |

---

## Abstract

Forests in Bangladesh are disappearing at an alarming rate due to industrial expansion, urban growth, and agricultural encroachment. This proposal presents **EcoVision**, a research project that applies deep learning and machine learning techniques to Google Earth satellite imagery spanning 1984 to 2022 to detect, map, and quantify deforestation across three study regions: Gazipur district, the Chittagong Hill Tracts, and the Sylhet hill forest area. By comparing multi-temporal satellite images using models such as U-Net, Siamese Networks, Convolutional Neural Networks, Vision Transformers, Random Forest, and Support Vector Machines, the study aims to produce high-accuracy deforestation maps, area statistics, and an interactive change monitoring dashboard on Google Earth Engine. The Gazipur case study is given primary focus due to the extreme and well-documented pace of Sal forest loss driven by industrial urbanisation north of Dhaka.

**Keywords:** Deforestation Detection, Deep Learning, Remote Sensing, Satellite Imagery, U-Net, Change Detection, Bangladesh, Google Earth Engine

---

## 1. Introduction

Bangladesh is one of the most densely populated countries in the world. As the population grows and industries expand, forests are cleared to make way for settlements, factories, roads, and farms. Three regions are under particularly severe pressure:

| Region | Primary deforestation drivers |
|---|---|
| **Gazipur** | Rapid industrialisation and urban sprawl destroying the Sal forest belt north of Dhaka |
| **Chittagong Hill Tracts (CHT)** | Shifting agriculture, commercial logging, road construction, resettlement |
| **Sylhet Hill Tracts** | Tea garden expansion, infrastructure projects, fuelwood extraction |

Without an automated system, monitoring these changes requires costly and slow field surveys. Satellite remote sensing, combined with modern deep learning, offers a scalable and repeatable solution. Google Earth provides historical imagery going back to 1984 for most parts of Bangladesh, making long-term comparison feasible at no data cost. This research proposes using that imagery alongside state-of-the-art machine learning and deep learning models to detect, map, and quantify deforestation automatically.

### 1.1 Problem Statement

Deforestation in Bangladesh is an ongoing and escalating environmental crisis. Despite its severity, systematic and automated monitoring of forest change remains limited. Current approaches rely heavily on field surveys, which are time-consuming, spatially limited, and expensive. Remote sensing data is widely available but underutilised for automated, large-scale, multi-temporal forest change detection in Bangladesh's specific landscape types. There is therefore a need for an intelligent deep learning framework that can analyse freely available satellite imagery to detect and quantify deforestation across ecologically important regions at scale.

### 1.2 Objectives

1. **Dataset construction** — Build a labelled multi-temporal satellite image dataset for Gazipur, the Chittagong Hill Tracts, and Sylhet by acquiring and preprocessing Google Earth Engine imagery (Landsat and Sentinel-2, 1984–2022) and annotating forest / non-forest land cover using Bangladesh Forest Department shapefiles and the Hansen Global Forest Change dataset.
2. **Model development and comparison** — Develop and comparatively evaluate a suite of deep learning models (U-Net, Siamese Network, Swin Transformer) and traditional machine learning baselines (Random Forest, SVM, XGBoost) for pixel-level forest cover classification and bitemporal change detection, identifying the most accurate and computationally feasible approach for Bangladesh's forest landscapes.
3. **Output and dissemination** — Produce spatially explicit deforestation maps and quantitative area statistics for each study region, and disseminate the findings through an interactive Google Earth Engine dashboard and a peer-reviewed publication.

### 1.3 Research Questions

| # | Research question |
|---|---|
| RQ1 | How much forest cover has been lost in Gazipur, the Chittagong Hill Tracts, and Sylhet between 1984 and 2022? |
| RQ2 | Which deep learning model (U-Net, CNN, Siamese Network, Vision Transformer, or ConvLSTM) performs best for semantic segmentation and change detection of forest loss in Bangladesh's satellite imagery? |
| RQ3 | How do traditional machine learning methods (Random Forest, SVM, XGBoost) compare against deep learning approaches for this task? |
| RQ4 | Which change detection method (PCC, NDVI Differencing, or LandTrendr) most accurately maps the location and timing of deforestation? |

---

## 2. Literature Review

Remote sensing-based forest change detection has a long history. Early work used simple spectral index thresholding and post-classification comparison on Landsat imagery to detect land cover transitions [1]. The availability of cloud computing platforms such as Google Earth Engine has dramatically expanded the scale at which change detection can be performed, enabling analysis of entire countries over multi-decadal periods [2].

The introduction of deep learning to remote sensing has further advanced detection accuracy. U-Net and its variants have become the dominant architecture for semantic segmentation of satellite images, consistently outperforming traditional classifiers on land cover mapping tasks [3]. Siamese Networks have been proposed specifically for bitemporal change detection, learning to directly compare image pairs rather than classifying each date independently [4]. Vision Transformers have more recently demonstrated state-of-the-art performance on remote sensing segmentation benchmarks by capturing long-range spatial context through attention mechanisms [5].

Studies specific to Bangladesh have used moderate-resolution Landsat imagery and vegetation index differencing to document national-level forest loss, but detailed, region-specific deep learning studies combining multiple methods remain scarce [6]. This research fills that gap by applying a comprehensive suite of deep learning and machine learning methods to three ecologically distinct and threatened forest regions of Bangladesh.

### 2.1 Comparison of Existing Studies

**Table 1: Literature review comparison of existing studies on deforestation detection**

| Ref. | Study Focus | Dataset / Source | Technique Used | Findings | Limitations / Gap |
|---|---|---|---|---|---|
| [1] | National-scale forest loss mapping | Landsat, Hansen GFC | Post-classification comparison, spectral thresholding | Mapped global forest cover loss 2000–2012 | Limited to moderate resolution; no deep learning |
| [2] | Cloud-based large-scale land cover change | Google Earth Engine, Landsat | NDVI differencing, random forest | Enabled country-scale analysis without local computing | No temporal trajectory modelling; limited to two dates |
| [3] | Semantic segmentation of remote sensing images | ISPRS, DeepGlobe datasets | U-Net, SegNet | U-Net outperforms traditional classifiers on pixel-level segmentation | Not validated on Bangladesh-specific forest classes |
| [4] | Bitemporal change detection in urban/forest areas | LEVIR-CD, WHU-CD datasets | Siamese Network, CNNs | Direct image-pair comparison reduces error accumulation | Tested mainly on urban change; forest-specific application limited |
| [5] | Attention-based remote sensing segmentation | DOTA, POTSDAM datasets | Swin Transformer, ViT | Outperforms CNN-based models on complex scene segmentation | High computational requirements; needs large training data |
| [6] | Forest cover change in Bangladesh | Landsat, MODIS | NDVI differencing, field surveys | Documented significant forest loss but methods not automated | No deep learning; coarse spatial resolution; no region-specific detail |

---

## 3. Methodology / Research Framework

The proposed research framework consists of eight stages: image collection, preprocessing, ground truth labelling, model training, classification, change detection, analysis, and visualisation. Multi-temporal Google Earth / Google Earth Engine imagery for the three study regions forms the primary data source, spanning 1984 to 2022.

### 3.1 Proposed Methodology

| Step | Stage | Details |
|---|---|---|
| 1 | **Image Collection** | Download Landsat 4/5, 7, 8/9 and Sentinel-2 imagery from Google Earth Engine for Gazipur, CHT, and Sylhet covering 1984–2022 |
| 2 | **Preprocessing** | Apply cloud masking, median compositing, band normalisation, and compute vegetation indices (NDVI, EVI, NDWI, SAVI) |
| 3 | **Ground Truth Labelling** | Prepare forest / non-forest labels from Bangladesh Forest Department shapefiles and the Hansen Global Forest Change dataset; split into training and test sets |
| 4 | **Model Training** | Train deep learning models (U-Net, CNN/ResNet-50, Siamese Network, Swin Transformer, ConvLSTM) and traditional ML models (Random Forest, SVM, XGBoost) on labelled image patches |
| 5 | **Classification** | Apply trained models to 1984 and 2022 composites to produce annual forest cover maps for all three regions |
| 6 | **Change Detection** | Compare 1984 and 2022 maps using Post-Classification Comparison, NDVI Differencing, Siamese Network direct comparison, and LandTrendr time-series analysis |
| 7 | **Analysis and Quantification** | Calculate deforestation area statistics in hectares and as a percentage of original cover; produce hotspot maps |
| 8 | **Visualisation and Reporting** | Export results as maps and charts; build an interactive Google Earth Engine dashboard; write thesis and submit conference/journal paper |

### 3.2 Research Architecture / Workflow Diagram

> **Figure 1: Workflow diagram of the EcoVision deforestation detection framework.**
> The original figure is a nine-stage pipeline diagram (Roman numerals denote pipeline stages; dashed horizontal lines separate stages; a dashed vertical arrow on the right denotes the accuracy assessment feedback loop from Stage V back to Stage III/IV). Its contents are transcribed below.

#### Stage I — Data Sources

| Source | Provider / Archive | Specification |
|---|---|---|
| Landsat 4/5/7/8/9 | USGS / GEE archive | 30 m spatial resolution · 1984–2022 |
| Sentinel-2 MSI | ESA Copernicus · GEE | 10 m spatial resolution · 2017–2022 |
| Hansen GFC Dataset | Global forest cover change | Baseline labels · forest loss 2000–2022 |

#### Stage II — Preprocessing
- Cloud masking · median compositing · band normalisation
- Vegetation indices: NDVI · EVI · NDWI · SAVI

#### Stage III — Ground Truth Labelling and Dataset Preparation
- BFD shapefiles · Hansen GFC labels · forest / non-forest patch extraction
- Training / validation / test split: **70 / 15 / 15**

#### Stage IV — Model Training (two parallel branches)

| Deep Learning branch | Traditional ML branch |
|---|---|
| U-Net with ResNet-50 backbone | Random Forest classifier |
| Siamese Network (bitemporal) | Support Vector Machine (SVM) |
| Swin Transformer / Vision Transformer | XGBoost |
| ConvLSTM (temporal sequence modelling) | Feature vectors: NDVI · EVI · spectral bands |
| Frameworks: PyTorch · segmentation-models-pytorch · timm | Frameworks: Scikit-learn · XGBoost library |

#### Stage V — Annual Forest Cover Classification (1984–2022)
- Forest / non-forest maps generated per composite year · applied across all three study regions
- Accuracy metrics: Overall Accuracy · F1 score · IoU · Kappa coefficient
- *(Feedback loop: accuracy assessment feeds back into dataset preparation and model training)*

#### Stage VI — Change Detection Methods
- Post-Classification Comparison (PCC) · NDVI Differencing · Siamese direct comparison
- LandTrendr temporal segmentation (Google Earth Engine)

#### Stage VII — Regional Application

| Gazipur District | Chittagong Hill Tracts | Sylhet Hill Forest Area |
|---|---|---|
| Sal forest loss mapping | Shifting agriculture impact | Tea garden expansion |
| Industrial urbanisation drivers | Commercial logging pressure | Infrastructure development |
| North Dhaka peri-urban growth | Road construction corridors | Fuelwood extraction zones |
| Primary case study focus | Resettlement-driven clearance | Remnant forest fragmentation |
| 1984 vs 2022 endpoint comparison | Multi-decadal trajectory analysis | Biodiversity hotspot monitoring |

#### Stage VIII — Quantification and Method Comparison
- Forest loss area (hectares) · percentage of original cover lost · spatial hotspot maps
- DL vs ML benchmark: OA · F1 · IoU · Kappa · inference time comparison

#### Stage IX — Outputs

| Output | Description |
|---|---|
| GEE Interactive Dashboard | Annual deforestation change maps · publicly accessible web interface |
| Thesis Document | Full methods, results, discussion · Dept. of ETE, UFTB submission |
| Conference / Journal Paper | IEEE TGRS · IEEE Access target · peer-reviewed publication |

---

## 4. Tools and Technologies

| Category | Tools |
|---|---|
| Programming Language | Python |
| Remote Sensing Platform | Google Earth Engine (JavaScript / Python API) |
| Data Analysis Libraries | Pandas, NumPy, Rasterio, GDAL |
| Deep Learning Frameworks | PyTorch, TensorFlow / Keras |
| Machine Learning Libraries | Scikit-learn, XGBoost |
| Segmentation Architectures | segmentation-models-pytorch (U-Net, ResNet backbone), timm (Swin Transformer) |
| Change Detection | LandTrendr (GEE), custom Siamese Network (PyTorch) |
| Visualisation | Matplotlib, Seaborn, Folium, Google Earth Engine Map |
| Development Environment | Jupyter Notebook / Google Colab (GPU runtime) / VS Code |
| Ground Truth Data | Bangladesh Forest Department Shapefiles, Hansen Global Forest Change (GFC) Dataset |

---

## 5. Expected Results / Outcomes

1. **Deforestation maps** for Gazipur, Chittagong Hill Tracts, and Sylhet covering 1984–2022, showing exactly where and how much forest has been lost.
2. **A trained deep learning model** (U-Net based) capable of classifying forest vs. non-forest from Google Earth imagery with at least **85% overall accuracy**.
3. **A quantitative comparison** of multiple ML and DL methods, showing which performs best for Bangladesh's specific forest types and landscapes.
4. **Area statistics** reporting forest loss in hectares and as a percentage of original cover for each study region.
5. **An interactive map dashboard** on Google Earth Engine showing annual forest change across all three regions.
6. **A thesis document** and at least one submitted conference or journal paper.

---

## 6. Work Plan

This section presents the planned 12-month timeline of the EcoVision project, detailing the major tasks and their duration. It helps in organising and monitoring the overall progress of the research.

### 6.1 Gantt Chart

> **Figure 2: Gantt chart for the proposed 12-month EcoVision research project.**
> The chart spans January–December. Tasks are listed below in their pipeline order as shown in the figure; exact bar start/end months are rendered graphically in the original and are not reproduced numerically here.

| # | Task |
|---|---|
| 1 | Literature Review and Problem Formulation |
| 2 | Data Collection and Preprocessing (GEE) |
| 3 | Ground Truth Labelling and Dataset Preparation |
| 4 | Baseline ML Model Training (RF, SVM, XGBoost) |
| 5 | Deep Learning Model Training (U-Net, Siamese, ViT) |
| 6 | Change Detection and Deforestation Mapping |
| 7 | Results Evaluation and Method Comparison |
| 8 | Thesis Writing and Paper Submission |

---

## 7. Conclusion

EcoVision addresses a clear and urgent need: automated, evidence-based monitoring of deforestation in Bangladesh using freely available satellite imagery. By combining the historical depth of Google Earth's image archive (back to 1984) with state-of-the-art deep learning models including U-Net, Siamese Networks, and Vision Transformers, alongside traditional methods such as Random Forest and SVM, this study will produce a comprehensive picture of forest loss across Gazipur, the Chittagong Hill Tracts, and Sylhet. The Gazipur case study — comparing 1984 and 2022 imagery — offers a particularly striking illustration of how industrial and urban growth can devastate a forest ecosystem within a single generation. The outcomes of this research will be directly useful to forest managers, policymakers, and conservation organisations working to protect Bangladesh's remaining natural forests.

---

## References

| # | Reference |
|---|---|
| [1] | M. C. Hansen et al., "High-resolution global maps of 21st-century forest cover change," *Science*, vol. 342, no. 6160, pp. 850–853, Nov. 2013. |
| [2] | N. Gorelick, M. Hancher, M. Dixon, S. Ilyushchenko, D. Thau, and R. Moore, "Google Earth Engine: Planetary-scale geospatial analysis for everyone," *Remote Sensing of Environment*, vol. 202, pp. 18–27, Dec. 2017. |
| [3] | O. Ronneberger, P. Fischer, and T. Brox, "U-Net: Convolutional networks for biomedical image segmentation," in *Proc. Int. Conf. Medical Image Computing and Computer-Assisted Intervention (MICCAI)*, Munich, Germany, 2015, pp. 234–241. |
| [4] | H. Chen, C. Wu, B. Du, P. Du, and L. Wang, "Change detection in multisource VHR images via deep Siamese convolutional multiple-layers recurrent neural network," *IEEE Trans. Geoscience and Remote Sensing*, vol. 58, no. 4, pp. 2848–2864, Apr. 2020. |
| [5] | Z. Liu et al., "Swin Transformer: Hierarchical vision transformer using shifted windows," in *Proc. IEEE/CVF Int. Conf. Computer Vision (ICCV)*, 2021, pp. 10012–10022. |
| [6] | A. Islam, M. Islam, and M. Rahman, "Spatiotemporal analysis of deforestation and its drivers in Bangladesh using remote sensing and GIS techniques," *Environmental Monitoring and Assessment*, vol. 190, no. 10, p. 571, Oct. 2018. |
| [7] | R. Kennedy, Z. Yang, and W. Cohen, "Detecting trends in forest disturbance and recovery using yearly Landsat time series: 1. LandTrendr — Temporal segmentation algorithms," *Remote Sensing of Environment*, vol. 114, no. 12, pp. 2897–2910, Dec. 2010. |
| [8] | G. Cheng, J. Han, and X. Lu, "Remote sensing image scene classification: Benchmark and state of the art," *Proceedings of the IEEE*, vol. 105, no. 10, pp. 1865–1883, Oct. 2017. |

> **Note:** References [7] (LandTrendr) and [8] (scene classification benchmark) appear in the reference list but are not cited inline in the proposal body.
