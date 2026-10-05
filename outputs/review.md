# Executed study review

All economic series are normalized to EUR before returns and covariance. Synthetic raw observations describe the constructed native NAV over the study interval; their symbols identify the underlying source.

## provenance

```text
                                   Provider    Symbol                                        Instrument / benchmark                Return type Native currency Converted to FX series used Raw start date Raw end date  Raw observations  Raw missing observations  FX missing on observed sessions Configured usable start  Pre-usable source observations excluded  EUR observations Final common start Final common end  Final common observations                                                              Distributions                                                                                                                                                                                                                         Limitation                                                                                                Reference
Asset                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       
Apple                         Yahoo Finance      AAPL                                             Primary US equity             Adjusted price             USD          EUR       EURUSD=X     1980-12-12   2026-10-02             11544                         0                             5828                    None                                        0              5716         2019-09-05       2026-10-02                       1763    Yahoo split/dividend adjustment; reinvestment proxy before investor tax                                                                                                                                                         Adjusted prices are a vendor proxy, not an independently audited TR index.                                                                                                         
Nasdaq 100                    Yahoo Finance       QQQ                    Invesco QQQ ETF; Nasdaq-100 exposure proxy             Adjusted price             USD          EUR       EURUSD=X     1999-03-10   2026-10-02              6935                         0                             1219                    None                                        0              5716         2019-09-05       2026-10-02                       1763         Yahoo dividend/split adjustments; distributions assumed reinvested                                                                                      Exact Nasdaq-100 TR unavailable from tested Yahoo ^XNDX. QQQ is an ETF proxy with fund fees/tracking differences, not the gross TR benchmark.                                                             https://www.invesco.com/qqq-etf/en/home.html
S&P 500                       Yahoo Finance  ^SP500TR                                    S&P 500 Total Return index               Gross Return             USD          EUR       EURUSD=X     1988-01-04   2026-10-02              9761                         0                             4045                    None                                        0              5716         2019-09-05       2026-10-02                       1763                            Gross dividends reinvested by index methodology                                                                                                                                                                                                                                                                                    https://www.spglobal.com/spdji/en/indices/equity/sp-500/
Dow Jones                     Yahoo Finance       DIA      State Street SPDR Dow Jones Industrial Average ETF proxy             Adjusted price             USD          EUR       EURUSD=X     1998-01-20   2026-10-02              7221                         0                             1505                    None                                        0              5716         2019-09-05       2026-10-02                       1763         Yahoo dividend/split adjustments; distributions assumed reinvested                                                                                      Exact Dow Jones TR unavailable from tested Yahoo ^DJITR. DIA is an ETF proxy with fund fees/tracking differences, not the gross TR benchmark.  https://www.ssga.com/us/en/individual/etfs/state-street-spdr-dow-jones-industrial-average-etf-trust-dia
CAC 40                        Yahoo Finance   CACC.PA               Amundi CAC 40 UCITS ETF Acc; FR0013380607 proxy             Adjusted price             EUR          EUR           None     2018-12-13   2026-10-02              1998                         0                                0              2019-09-05                                      184              1814         2019-09-05       2026-10-02                       1763       Accumulating share class reinvests within fund; Yahoo adjusted close  Exact CAC 40 GR unavailable from tested Yahoo ^PX1GR. ETF proxy includes fees/tracking effects. Vendor history before issuer-reported 2019-09-05 share-class creation is excluded from the study; lineage discrepancy unresolved.         https://www.amundietf.fr/pdfDocuments/monthly-factsheet/FR0013380607/FRA/FRA/RETAIL/ETF/20251130
Gold                          Yahoo Finance      GC=F                 Yahoo continuous COMEX gold futures quotation               Price Return             USD          EUR       EURUSD=X     2000-08-30   2026-10-02              6548                        83                              840                    None                                        0              5708         2019-09-05       2026-10-02                       1763                            No dividends; quoted futures price changes only                                                                                                            Not spot gold or an investable futures total-return index: roll, collateral yield and contract stitching are unmodeled.                                                                                                         
Apple x1.5     Synthetic from Yahoo Finance      AAPL                         1.5x daily reset of Primary US equity  Synthetic daily-reset NAV             USD          EUR       EURUSD=X     2019-09-05   2026-10-02              1779                         0                                1                    None                                        0              1778         2019-09-05       2026-10-02                       1763  Inherited from underlying; native-currency daily reset, then unlevered FX                                                                                        Financing, fees, tracking error, trading costs and tax excluded. Adjusted prices are a vendor proxy, not an independently audited TR index.                                                                                                         
Nasdaq 100 x2  Synthetic from Yahoo Finance       QQQ  2x daily reset of Invesco QQQ ETF; Nasdaq-100 exposure proxy  Synthetic daily-reset NAV             USD          EUR       EURUSD=X     2019-09-05   2026-10-02              1779                         0                                1                    None                                        0              1778         2019-09-05       2026-10-02                       1763  Inherited from underlying; native-currency daily reset, then unlevered FX                     Financing, fees, tracking error, trading costs and tax excluded. Exact Nasdaq-100 TR unavailable from tested Yahoo ^XNDX. QQQ is an ETF proxy with fund fees/tracking differences, not the gross TR benchmark.                                                             https://www.invesco.com/qqq-etf/en/home.html
```

## fx-validation

```text
            USD value    EURUSD  Computed EUR value
Date                                               
2019-09-05  51.166752  1.103497           46.367820
2019-09-06  51.161949  1.103631           46.357839
2019-09-09  51.380272  1.102062           46.621944
2019-09-10  51.987236  1.104838           47.054165
2019-09-11  53.640171  1.105033           48.541674
```

## asset-performance

```text
                   CAGR  Mean return annualized  Volatility annualized  Max Drawdown    Sharpe    Calmar
Asset                                                                                                   
Apple x1.5     0.432433                0.473959               0.469798     -0.486864  1.008858  0.888201
Apple          0.299947                0.315998               0.317996     -0.362696  0.993718  0.826994
Nasdaq 100     0.216618                0.230909               0.254573     -0.308661  0.907044  0.701799
Nasdaq 100 x2  0.398013                0.461761               0.493791     -0.595887  0.935135  0.667933
Gold           0.150381                0.161262               0.197061     -0.229469  0.818333  0.655340
S&P 500        0.158501                0.171141               0.210543     -0.331651  0.812854  0.477917
Dow Jones      0.112811                0.128817               0.202714     -0.357461  0.635463  0.315591
CAC 40         0.078667                0.094725               0.189835     -0.386470  0.498987  0.203552
```

## leverage-diagnostics

```text
           Asset  Underlying  Leverage  Reset sessions  Worst underlying return Wipeout date
0     Apple x1.5       Apple       1.5            1779                -0.128647          NaT
1  Nasdaq 100 x2  Nasdaq 100       2.0            1779                -0.119788          NaT
```

## portfolio-results

```text
                        CAGR Mean return annualized Volatility Max Drawdown    Sharpe    Calmar Success Solver status                                       Status Risk ceiling                                                    Main Allocation
Portfolio                                                                                                                                                                                                                                         
Minimum Volatility  0.126919               0.130494   0.138136    -0.263359  0.944675  0.481922    True             0         Optimization terminated successfully          NaN         Gold 42.4% · CAC 40 38.7% · Dow Jones 16.3% · S&P 500 2.6%
Maximum CAGR        0.437657               0.470724   0.454283    -0.467737  1.036191   0.93569    True             0         Optimization terminated successfully          NaN                             Apple x1.5 73.5% · Nasdaq 100 x2 26.5%
Maximum Sharpe      0.256949               0.251729   0.201127    -0.235927   1.25159  1.089101    True             0         Optimization terminated successfully          NaN  Gold 56.8% · Apple x1.5 25.3% · CAC 40 11.6% · Nasdaq 100 x2 6.4%
Prudent             0.172562               0.172396       0.15    -0.240332  1.149307  0.718014    True             0         Optimization terminated successfully         0.15        Gold 48.7% · CAC 40 30.1% · S&P 500 11.5% · Apple x1.5 9.6%
Modéré              0.255474               0.250314        0.2    -0.235748  1.251571   1.08367    True             0         Optimization terminated successfully          0.2  Gold 56.7% · Apple x1.5 25.1% · CAC 40 12.0% · Nasdaq 100 x2 6.2%
Dynamique           0.355142               0.352649        0.3    -0.311913  1.175496  1.138591    True             0         Optimization terminated successfully          0.3                Apple x1.5 44.0% · Gold 38.1% · Nasdaq 100 x2 17.9%
Agressif            0.414575               0.431144        0.4    -0.412476   1.07786  1.005088    True             0         Optimization terminated successfully          0.4                Apple x1.5 60.5% · Nasdaq 100 x2 26.8% · Gold 12.6%
Très agressif       0.437657               0.470724   0.454283    -0.467737  1.036191   0.93569    True             0  Maximum CAGR reached; unused risk allowance          0.5                             Apple x1.5 73.5% · Nasdaq 100 x2 26.5%
```

## portfolio-weights

```text
                      Apple x1.5  Nasdaq 100 x2       S&P 500     Dow Jones        CAC 40      Gold
Portfolio                                                                                          
Minimum Volatility  4.805372e-17   0.000000e+00  2.588045e-02  1.628930e-01  3.868376e-01  0.424389
Maximum CAGR        7.347462e-01   2.652538e-01  8.267211e-17  0.000000e+00  0.000000e+00  0.000000
Maximum Sharpe      2.529418e-01   6.352105e-02  7.286760e-18  6.964686e-17  1.159530e-01  0.567584
Prudent             9.601359e-02   1.481590e-17  1.154853e-01  1.305877e-16  3.010346e-01  0.487467
Modéré              2.511116e-01   6.169861e-02  0.000000e+00  1.541600e-18  1.203829e-01  0.566807
Dynamique           4.397554e-01   1.792902e-01  0.000000e+00  3.247286e-17  2.657709e-17  0.380954
Agressif            6.052681e-01   2.682739e-01  5.747224e-17  4.820486e-17  0.000000e+00  0.126458
Très agressif       7.347462e-01   2.652538e-01  8.267211e-17  0.000000e+00  0.000000e+00  0.000000
```

## covariance

```text
               Apple x1.5  Nasdaq 100 x2   S&P 500  Dow Jones    CAC 40      Gold
Apple x1.5       0.220710       0.179755  0.074286   0.063885  0.027532  0.010089
Nasdaq 100 x2    0.179755       0.243829  0.095261   0.078049  0.038331  0.015510
S&P 500          0.074286       0.095261  0.044329   0.040420  0.020069  0.008451
Dow Jones        0.063885       0.078049  0.040420   0.041093  0.020822  0.007745
CAC 40           0.027532       0.038331  0.020069   0.020822  0.036037  0.002898
Gold             0.010089       0.015510  0.008451   0.007745  0.002898  0.038833
```

## frontier-dominance

```text
               100% CAGR  100% volatility  Frontier CAGR  Frontier volatility
Asset                                                                        
Apple x1.5      0.432433         0.469798       0.437657             0.454283
Nasdaq 100 x2   0.398013         0.493791       0.437657             0.454283
S&P 500         0.158501         0.210543       0.268943             0.210543
Dow Jones       0.112811         0.202714       0.259010             0.202714
CAC 40          0.078667         0.189835       0.241721             0.189835
Gold            0.150381         0.197061       0.251585             0.197061
```

## solver-log

```text
                 Portfolio  Success  Status                               Message  Iterations          ftol  Raw minimum weight  Raw weight sum
0       Minimum Volatility     True       0  Optimization terminated successfully          14  1.000000e-10        0.000000e+00             1.0
1             Maximum CAGR     True       0  Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
2   Maximum Sharpe start 0     True       0  Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
3   Maximum Sharpe start 1     True       0  Optimization terminated successfully          11  1.000000e-10        0.000000e+00             1.0
4   Maximum Sharpe start 2     True       0  Optimization terminated successfully          11  1.000000e-10        0.000000e+00             1.0
5   Maximum Sharpe start 3     True       0  Optimization terminated successfully          12  1.000000e-10        7.286760e-18             1.0
6   Maximum Sharpe start 4     True       0  Optimization terminated successfully          10  1.000000e-10        5.217744e-17             1.0
7   Maximum Sharpe start 5     True       0  Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
8   Maximum Sharpe start 6     True       0  Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
9   Maximum Sharpe start 7     True       0  Optimization terminated successfully          12  1.000000e-10        0.000000e+00             1.0
10  Maximum Sharpe start 8     True       0  Optimization terminated successfully          11  1.000000e-10        0.000000e+00             1.0
11              Frontier 1     True       0  Optimization terminated successfully          12  1.000000e-10        3.054277e-17             1.0
12              Frontier 2     True       0  Optimization terminated successfully          13  1.000000e-10        0.000000e+00             1.0
13              Frontier 3     True       0  Optimization terminated successfully          14  1.000000e-10        0.000000e+00             1.0
14              Frontier 4     True       0  Optimization terminated successfully          13  1.000000e-10        0.000000e+00             1.0
15              Frontier 5     True       0  Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
16              Frontier 6     True       0  Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
17              Frontier 7     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
18              Frontier 8     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
19              Frontier 9     True       0  Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
20             Frontier 10     True       0  Optimization terminated successfully          10  1.000000e-10        1.082670e-17             1.0
21             Frontier 11     True       0  Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
22             Frontier 12     True       0  Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
23             Frontier 13     True       0  Optimization terminated successfully          11  1.000000e-10        0.000000e+00             1.0
24             Frontier 14     True       0  Optimization terminated successfully          11  1.000000e-10        1.221670e-17             1.0
25             Frontier 15     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
26             Frontier 16     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
27             Frontier 17     True       0  Optimization terminated successfully           9  1.000000e-10        5.123415e-17             1.0
28             Frontier 18     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
29             Frontier 19     True       0  Optimization terminated successfully           9  1.000000e-10        1.673959e-17             1.0
30             Frontier 20     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
31             Frontier 21     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
32             Frontier 22     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
33             Frontier 23     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
34             Frontier 24     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
35             Frontier 25     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
36             Frontier 26     True       0  Optimization terminated successfully           9  1.000000e-10        2.851060e-17             1.0
37             Frontier 27     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
38             Frontier 28     True       0  Optimization terminated successfully           9  1.000000e-10        1.374311e-18             1.0
39             Frontier 29     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
40             Frontier 30     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
41             Frontier 31     True       0  Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
42             Frontier 32     True       0  Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
43             Frontier 33     True       0  Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
44             Frontier 34     True       0  Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
45             Frontier 35     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
46             Frontier 36     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
47             Frontier 37     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
48             Frontier 38     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
49             Frontier 39     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
50             Frontier 40     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
51             Frontier 41     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
52             Frontier 42     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
53             Frontier 43     True       0  Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
54             Frontier 44     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
55             Frontier 45     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
56             Frontier 46     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
57             Frontier 47     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
58             Frontier 48     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
59                 Prudent     True       0  Optimization terminated successfully          13  1.000000e-10        1.481590e-17             1.0
60                  Modéré     True       0  Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
61               Dynamique     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
62                Agressif     True       0  Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
63       Dominance S&P 500     True       0  Optimization terminated successfully          11  1.000000e-10        0.000000e+00             1.0
64     Dominance Dow Jones     True       0  Optimization terminated successfully          12  1.000000e-10        0.000000e+00             1.0
65        Dominance CAC 40     True       0  Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
66          Dominance Gold     True       0  Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
```

## frontier

```text
        CAGR  Mean return annualized  Volatility  Max Drawdown    Sharpe    Calmar  Success  Solver status                                       Status  Risk ceiling  Weight: Apple x1.5  Weight: Nasdaq 100 x2  Weight: S&P 500  Weight: Dow Jones  Weight: CAC 40  Weight: Gold
0   0.126919                0.130494    0.138136     -0.263359  0.944675  0.481922     True              0                Minimum achievable volatility      0.138136        4.805372e-17           0.000000e+00     2.588045e-02       1.628930e-01    3.868376e-01      0.424389
1   0.158309                0.159217    0.144588     -0.244465  1.101180  0.647571     True              0         Optimization terminated successfully      0.144588        5.553076e-02           3.054277e-17     1.606484e-01       8.976755e-17    3.155540e-01      0.468267
2   0.175003                0.174658    0.151040     -0.239623  1.156372  0.730327     True              0         Optimization terminated successfully      0.151040        1.029626e-01           8.075136e-19     1.077335e-01       0.000000e+00    2.985419e-01      0.490762
3   0.188798                0.187470    0.157492     -0.235611  1.190349  0.801313     True              0         Optimization terminated successfully      0.157492        1.423177e-01           3.166654e-17     6.383544e-02       0.000000e+00    2.844234e-01      0.509423
4   0.200978                0.198827    0.163944     -0.232716  1.212774  0.863621     True              0         Optimization terminated successfully      0.163944        1.772015e-01           0.000000e+00     2.493079e-02       0.000000e+00    2.719060e-01      0.525962
5   0.212209                0.209330    0.170396     -0.233709  1.228491  0.908004     True              0         Optimization terminated successfully      0.170396        1.935750e-01           1.464805e-02     7.476839e-18       0.000000e+00    2.534566e-01      0.538320
6   0.222616                0.219105    0.176848     -0.234115  1.238947  0.950884     True              0         Optimization terminated successfully      0.176848        2.072939e-01           2.587456e-02     0.000000e+00       1.330358e-17    2.217159e-01      0.545116
7   0.232365                0.228307    0.183300     -0.234544  1.245540  0.990711     True              0         Optimization terminated successfully      0.183300        2.202109e-01           3.644016e-02     0.000000e+00       2.747081e-17    1.918365e-01      0.551512
8   0.241605                0.237073    0.189752     -0.234993  1.249383  1.028136     True              0         Optimization terminated successfully      0.189752        2.325168e-01           4.650223e-02     0.000000e+00       0.000000e+00    1.633763e-01      0.557605
9   0.250437                0.245493    0.196204     -0.235463  1.251216  1.063596     True              0         Optimization terminated successfully      0.196204        2.443412e-01           5.616667e-02     6.320036e-17       0.000000e+00    1.360353e-01      0.563457
10  0.258934                0.253635    0.202656     -0.235952  1.251557  1.097401     True              0         Optimization terminated successfully      0.202656        2.557761e-01           6.550886e-02     1.082670e-17       1.349055e-16    1.096005e-01      0.569115
11  0.267149                0.261547    0.209108     -0.236461  1.250775  1.129779     True              0         Optimization terminated successfully      0.209108        2.668895e-01           7.458455e-02     0.000000e+00       1.127958e-16    8.391470e-02      0.574611
12  0.275121                0.269265    0.215560     -0.236989  1.249141  1.160904     True              0         Optimization terminated successfully      0.215560        2.777332e-01           8.343608e-02     3.578348e-17       0.000000e+00    5.885805e-02      0.579973
13  0.282883                0.276818    0.222012     -0.237535  1.246861  1.190908     True              0         Optimization terminated successfully      0.222012        2.883476e-01           9.209651e-02     1.602878e-17       0.000000e+00    3.433723e-02      0.585219
14  0.290458                0.284229    0.228464     -0.238100  1.244087  1.219898     True              0         Optimization terminated successfully      0.228464        2.987648e-01           1.005921e-01     1.221670e-17       6.981075e-17    1.027802e-02      0.590365
15  0.297811                0.291475    0.234916     -0.242978  1.240764  1.225671     True              0         Optimization terminated successfully      0.234916        3.117329e-01           1.089352e-01     1.039344e-17       0.000000e+00    7.294619e-17      0.579332
16  0.304737                0.298399    0.241368     -0.250827  1.236286  1.214928     True              0         Optimization terminated successfully      0.241368        3.261932e-01           1.169311e-01     0.000000e+00       5.199798e-17    1.660829e-16      0.556876
17  0.311281                0.305042    0.247820     -0.258349  1.230904  1.204885     True              0         Optimization terminated successfully      0.247820        3.400720e-01           1.245952e-01     7.720499e-17       5.123415e-17    6.290102e-17      0.535333
18  0.317501                0.311453    0.254272     -0.265600  1.224885  1.195413     True              0         Optimization terminated successfully      0.254272        3.534731e-01           1.319853e-01     7.195772e-17       2.079605e-18    0.000000e+00      0.514542
19  0.323443                0.317671    0.260724     -0.272622  1.218419  1.186417     True              0         Optimization terminated successfully      0.260724        3.664747e-01           1.391450e-01     1.673959e-17       5.327573e-17    4.918106e-17      0.494380
20  0.329140                0.323722    0.267176     -0.279448  1.211647  1.177823     True              0         Optimization terminated successfully      0.267176        3.791371e-01           1.461079e-01     1.730460e-17       9.447906e-18    0.000000e+00      0.474755
21  0.334619                0.329632    0.273628     -0.286103  1.204674  1.169574     True              0         Optimization terminated successfully      0.273628        3.915083e-01           1.529007e-01     3.658090e-18       1.905475e-17    0.000000e+00      0.455591
22  0.339901                0.335418    0.280080     -0.292609  1.197581  1.161624     True              0         Optimization terminated successfully      0.280080        4.036267e-01           1.595446e-01     0.000000e+00       0.000000e+00    0.000000e+00      0.436829
23  0.345004                0.341095    0.286531     -0.298981  1.190428  1.153934     True              0         Optimization terminated successfully      0.286531        4.155236e-01           1.660574e-01     2.054314e-17       0.000000e+00    0.000000e+00      0.418419
24  0.349943                0.346676    0.292983     -0.305234  1.183262  1.146474     True              0         Optimization terminated successfully      0.292983        4.272255e-01           1.724532e-01     0.000000e+00       3.381375e-17    2.580781e-17      0.400321
25  0.354730                0.352172    0.299435     -0.311380  1.176119  1.139217     True              0         Optimization terminated successfully      0.299435        4.387542e-01           1.787443e-01     1.533813e-17       0.000000e+00    1.057997e-17      0.382501
26  0.359374                0.357590    0.305887     -0.317429  1.169026  1.132142     True              0         Optimization terminated successfully      0.305887        4.501284e-01           1.849409e-01     2.851060e-17       4.013888e-17    7.007366e-17      0.364931
27  0.363885                0.362940    0.312339     -0.323388  1.162005  1.125229     True              0         Optimization terminated successfully      0.312339        4.613639e-01           1.910517e-01     1.021160e-16       5.275512e-17    0.000000e+00      0.347584
28  0.368270                0.368227    0.318791     -0.329265  1.155072  1.118461     True              0         Optimization terminated successfully      0.318791        4.724737e-01           1.970850e-01     3.640802e-17       5.041921e-17    1.374311e-18      0.330441
29  0.372535                0.373457    0.325243     -0.335066  1.148239  1.111827     True              0         Optimization terminated successfully      0.325243        4.834720e-01           2.030450e-01     4.589410e-17       0.000000e+00    6.445709e-18      0.313483
30  0.376686                0.378635    0.331695     -0.340796  1.141516  1.105311     True              0         Optimization terminated successfully      0.331695        4.943671e-01           2.089396e-01     0.000000e+00       0.000000e+00    4.490333e-19      0.296693
31  0.380727                0.383766    0.338147     -0.346461  1.134908  1.098904     True              0         Optimization terminated successfully      0.338147        5.051688e-01           2.147731e-01     0.000000e+00       0.000000e+00    3.448239e-17      0.280058
32  0.384664                0.388853    0.344599     -0.352064  1.128421  1.092597     True              0         Optimization terminated successfully      0.344599        5.158853e-01           2.205498e-01     2.765880e-17       2.386155e-17    0.000000e+00      0.263565
33  0.388499                0.393900    0.351051     -0.358872  1.122057  1.082554     True              0         Optimization terminated successfully      0.351051        5.265238e-01           2.262736e-01     5.585123e-18       2.970587e-17    0.000000e+00      0.247203
34  0.392236                0.398909    0.357503     -0.366313  1.115819  1.070766     True              0         Optimization terminated successfully      0.357503        5.370908e-01           2.319478e-01     0.000000e+00       2.139616e-17    3.909417e-17      0.230961
35  0.395877                0.403884    0.363955     -0.373631  1.109707  1.059541     True              0         Optimization terminated successfully      0.363955        5.475917e-01           2.375759e-01     0.000000e+00       3.161074e-17    1.197662e-17      0.214832
36  0.399426                0.408827    0.370407     -0.380831  1.103722  1.048829     True              0         Optimization terminated successfully      0.370407        5.580332e-01           2.431591e-01     0.000000e+00       8.798131e-18    3.418625e-17      0.198808
37  0.402885                0.413740    0.376859     -0.387918  1.097862  1.038583     True              0         Optimization terminated successfully      0.376859        5.684180e-01           2.487021e-01     0.000000e+00       9.273317e-18    9.695669e-17      0.182880
38  0.406255                0.418625    0.383311     -0.394897  1.092127  1.028763     True              0         Optimization terminated successfully      0.383311        5.787514e-01           2.542059e-01     1.069695e-16       0.000000e+00    0.000000e+00      0.167043
39  0.409539                0.423484    0.389763     -0.401772  1.086516  1.019332     True              0         Optimization terminated successfully      0.389763        5.890372e-01           2.596725e-01     0.000000e+00       0.000000e+00    5.858440e-17      0.151290
40  0.412738                0.428318    0.396215     -0.408547  1.081025  1.010257     True              0         Optimization terminated successfully      0.396215        5.992792e-01           2.651037e-01     0.000000e+00       0.000000e+00    0.000000e+00      0.135617
41  0.415853                0.433130    0.402667     -0.415226  1.075653  1.001511     True              0         Optimization terminated successfully      0.402667        6.094803e-01           2.705012e-01     0.000000e+00       0.000000e+00    6.044448e-17      0.120018
42  0.418887                0.437921    0.409119     -0.421812  1.070399  0.993066     True              0         Optimization terminated successfully      0.409119        6.196437e-01           2.758665e-01     1.898667e-17       0.000000e+00    0.000000e+00      0.104490
43  0.421839                0.442691    0.415571     -0.428307  1.065259  0.984899     True              0         Optimization terminated successfully      0.415571        6.297721e-01           2.812009e-01     0.000000e+00       8.214663e-17    0.000000e+00      0.089027
44  0.424712                0.447442    0.422023     -0.434716  1.060231  0.976988     True              0         Optimization terminated successfully      0.422023        6.398681e-01           2.865056e-01     4.033889e-18       0.000000e+00    0.000000e+00      0.073626
45  0.427506                0.452175    0.428475     -0.441040  1.055312  0.969315     True              0         Optimization terminated successfully      0.428475        6.499340e-01           2.917817e-01     8.472024e-18       0.000000e+00    1.617653e-17      0.058284
46  0.430222                0.456891    0.434927     -0.447499  1.050500  0.961393     True              0         Optimization terminated successfully      0.434927        6.599721e-01           2.970303e-01     5.222747e-17       0.000000e+00    3.049806e-17      0.042998
47  0.432862                0.461591    0.441379     -0.454891  1.045792  0.951572     True              0         Optimization terminated successfully      0.441379        6.699842e-01           3.022522e-01     0.000000e+00       3.974056e-17    2.222911e-17      0.027764
48  0.435425                0.466276    0.447831     -0.462200  1.041186  0.942070     True              0         Optimization terminated successfully      0.447831        6.799725e-01           3.074483e-01     3.418276e-17       1.854780e-17    0.000000e+00      0.012579
49  0.437657                0.470724    0.454283     -0.467737  1.036191  0.935690     True              0  Maximum CAGR reached; unused risk allowance      0.454283        7.347462e-01           2.652538e-01     8.267211e-17       0.000000e+00    0.000000e+00      0.000000
```

## Numerical sanity checks

```json
{
  "portfolio_weight_sums": {
    "Minimum Volatility": 1.0,
    "Maximum CAGR": 1.0,
    "Maximum Sharpe": 1.0,
    "Prudent": 1.0,
    "Mod\u00e9r\u00e9": 1.0,
    "Dynamique": 1.0,
    "Agressif": 1.0,
    "Tr\u00e8s agressif": 1.0,
    "Frontier 0": 1.0,
    "Frontier 1": 1.0,
    "Frontier 2": 1.0,
    "Frontier 3": 1.0,
    "Frontier 4": 1.0,
    "Frontier 5": 1.0,
    "Frontier 6": 1.0,
    "Frontier 7": 1.0,
    "Frontier 8": 1.0,
    "Frontier 9": 1.0,
    "Frontier 10": 1.0,
    "Frontier 11": 1.0,
    "Frontier 12": 1.0,
    "Frontier 13": 1.0,
    "Frontier 14": 1.0,
    "Frontier 15": 1.0,
    "Frontier 16": 1.0,
    "Frontier 17": 1.0,
    "Frontier 18": 1.0,
    "Frontier 19": 1.0,
    "Frontier 20": 1.0,
    "Frontier 21": 1.0,
    "Frontier 22": 1.0,
    "Frontier 23": 1.0,
    "Frontier 24": 1.0,
    "Frontier 25": 1.0,
    "Frontier 26": 1.0,
    "Frontier 27": 1.0,
    "Frontier 28": 1.0,
    "Frontier 29": 0.9999999999999999,
    "Frontier 30": 1.0,
    "Frontier 31": 1.0,
    "Frontier 32": 1.0,
    "Frontier 33": 1.0,
    "Frontier 34": 1.0,
    "Frontier 35": 1.0,
    "Frontier 36": 0.9999999999999999,
    "Frontier 37": 1.0,
    "Frontier 38": 1.0,
    "Frontier 39": 1.0,
    "Frontier 40": 1.0,
    "Frontier 41": 1.0,
    "Frontier 42": 1.0,
    "Frontier 43": 0.9999999999999999,
    "Frontier 44": 1.0,
    "Frontier 45": 1.0,
    "Frontier 46": 1.0,
    "Frontier 47": 1.0,
    "Frontier 48": 1.0,
    "Frontier 49": 1.0
  },
  "minimum_portfolio_weight": 0.0,
  "largest_volatility_ceiling_violation": 1.5762224858661966e-11,
  "nonfinite_final_returns": 0,
  "common_observations": 1763,
  "return_observations": 1762,
  "common_start": "2019-09-05",
  "common_end": "2026-10-02",
  "covariance_minimum_eigenvalue": 0.0006830652416355062,
  "solver_attempts": 67,
  "unsuccessful_solver_attempts": 0
}
```