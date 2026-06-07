# Laboratory of Data Science — Music Streaming Decision Support System

This repository contains the project developed for the **Laboratory of Data Science** module of the **Decision Support Systems** course, part of the Master Programme in **Data Science and Business Informatics** at the **University of Pisa**.

The project simulates a complete **Decision Support System for a music streaming company**. Starting from raw data about songs and artists, the workflow covers data understanding, cleaning, song profiling, data warehouse design, ETL implementation, OLAP cube creation, MDX querying, and Power BI dashboarding.

The work follows the official project structure, composed of **22 incremental assignments**.

---

## Project Overview

The objective is to transform raw music streaming data into a structured analytical system that helps a music streaming company make data-driven decisions about artists, songs, categories, regions, release timing, and trending behavior.

The project is divided into four main phases:

1. **Python — Assignments 1–6**
   - Data understanding and cleaning
   - Song profiling through K-means clustering and topic modelling with pyLDAvis framework
   - Data warehouse schema design
   - Data preparation and upload into SQL Server

2. **SSIS — Assignments 7–13**
   - ETL workflows using SQL Server Integration Services
   - Business queries about artists, regions, seasons, streams, and trending behavior

3. **SSAS and MDX — Assignments 14–19**
   - OLAP cube creation from data warehouse
   - MDX queries for multidimensional business analysis

4. **Power BI — Assignments 20–22**
   - Interactive dashboards for business insights

---

## Repository Structure

```text
.
├── Data/                                  
│   ├── artists.xml
│   └── tracks.json
│
├── Task_1_ Data_Understanding/           
│
├── Task_2_Data_Cleaning/                
│
├── Task_3_Profiling/                     
│
├── Task_5_6_splitting_populating/        
│
├── Task_7_8_9_13/                         
│
├── Task_10_11_12/                        
│
├── Task_14/
│   └── Group_ID_2_CUBE/                  
│
├── Task 15-16-17-18-19-20-21-22/         
│
├── LDS-report-Group-ID-2.pdf              # Final project report
└── README.md
```
