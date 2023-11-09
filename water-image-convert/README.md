# Chlorophyll-a concentration

## Assessment of Human-Induced Effects on Sea/Brackish Water Chlorophyll-a Concentration in Ha Long Bay of Vietnam with Google Earth Engine

### Input

Data from [GEE](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED#description) (already processed by sen2cor).

### Output

$$
C = 10^{(a_{0} + a_{1} R + a_{2} R^{2} + a_{3} R^{3})} + a_{4}
$$

with

$$
\begin{aligned}
a_{0} &= 0.341 \\
a_{1} &= −3.0010 \\
a_{2} &= 2.811 \\
a_{3} &= −2.041 \\
a_{4} &= 0.0400
\end{aligned}
$$

and

$$
\begin{aligned}
R &= log(\frac{R_{rs}(490)}{R_{rs}(555)}) \\
R_{rs}(\lambda) &= \frac{\rho}{\pi} \\
\rho_{490} &= B2 \\
\rho_{555} &= B3
\end{aligned}
$$
