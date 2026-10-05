# Executed study review

All economic series are normalized to EUR before returns and covariance. Synthetic raw observations describe the constructed native NAV over the study interval; their symbols identify the underlying source.

## provenance

```text
                                   Provider    Symbol                                        Instrument / benchmark                Return type Native currency Converted to FX series used Raw start date Raw end date  Raw observations  Raw missing observations  FX missing on observed sessions  EUR observations Final common start Final common end  Final common observations                                                                  Distributions                                                                                                                                                                                                      Limitation                                                                                                Reference
Asset
Apple                         Yahoo Finance      AAPL                                             Primary US equity             Adjusted price             USD          EUR       EURUSD=X     1980-12-12   2026-10-02             11544                         0                             5828              5716         2003-12-01       2015-12-18                       2970        Yahoo split/dividend adjustment; reinvestment proxy before investor tax                                                                                                                                      Adjusted prices are a vendor proxy, not an independently audited TR index.
Nasdaq 100                    Yahoo Finance       QQQ                    Invesco QQQ ETF; Nasdaq-100 exposure proxy             Adjusted price             USD          EUR       EURUSD=X     1999-03-10   2026-10-02              6935                         0                             1219              5716         2003-12-01       2015-12-18                       2970             Yahoo dividend/split adjustments; distributions assumed reinvested                                                                   Exact Nasdaq-100 TR unavailable from tested Yahoo ^XNDX. QQQ is an ETF proxy with fund fees/tracking differences, not the gross TR benchmark.                                                             https://www.invesco.com/qqq-etf/en/home.html
S&P 500                       Yahoo Finance  ^SP500TR                                    S&P 500 Total Return index               Gross Return             USD          EUR       EURUSD=X     1988-01-04   2026-10-02              9761                         0                             4045              5716         2003-12-01       2015-12-18                       2970                                Gross dividends reinvested by index methodology                                                                                                                                                                                                                                                                 https://www.spglobal.com/spdji/en/indices/equity/sp-500/
Dow Jones                     Yahoo Finance       DIA      State Street SPDR Dow Jones Industrial Average ETF proxy             Adjusted price             USD          EUR       EURUSD=X     1998-01-20   2026-10-02              7221                         0                             1505              5716         2003-12-01       2015-12-18                       2970             Yahoo dividend/split adjustments; distributions assumed reinvested                                                                   Exact Dow Jones TR unavailable from tested Yahoo ^DJITR. DIA is an ETF proxy with fund fees/tracking differences, not the gross TR benchmark.  https://www.ssga.com/us/en/individual/etfs/state-street-spdr-dow-jones-industrial-average-etf-trust-dia
CAC 40                        Yahoo Finance  PX1GR.PA                                     CAC 40 Gross Return Index               Gross Return             EUR          EUR           None     1987-12-31   2015-12-18              7076                      2930                                0              7076         2003-12-01       2015-12-18                       2970  Gross dividends reinvested in index levels; no additional dividend adjustment                                                                                            Yahoo daily history has missing observations; inspect raw valid end and missing counts before interpreting coverage.                                           https://live.euronext.com/en/product/indices/QS0011131834-XPAR
Gold                          Yahoo Finance      GC=F                 Yahoo continuous COMEX gold futures quotation               Price Return             USD          EUR       EURUSD=X     2000-08-30   2026-10-02              6548                        83                              840              5708         2003-12-01       2015-12-18                       2970                                No dividends; quoted futures price changes only                                                                                         Not spot gold or an investable futures total-return index: roll, collateral yield and contract stitching are unmodeled.
Apple x1.5     Synthetic from Yahoo Finance      AAPL                         1.5x daily reset of Primary US equity  Synthetic daily-reset NAV             USD          EUR       EURUSD=X     2003-12-01   2015-12-18              3035                         0                               26              3009         2003-12-01       2015-12-18                       2970      Inherited from underlying; native-currency daily reset, then unlevered FX                                                                     Financing, fees, tracking error, trading costs and tax excluded. Adjusted prices are a vendor proxy, not an independently audited TR index.
Nasdaq 100 x2  Synthetic from Yahoo Finance       QQQ  2x daily reset of Invesco QQQ ETF; Nasdaq-100 exposure proxy  Synthetic daily-reset NAV             USD          EUR       EURUSD=X     2003-12-01   2015-12-18              3035                         0                               26              3009         2003-12-01       2015-12-18                       2970      Inherited from underlying; native-currency daily reset, then unlevered FX  Financing, fees, tracking error, trading costs and tax excluded. Exact Nasdaq-100 TR unavailable from tested Yahoo ^XNDX. QQQ is an ETF proxy with fund fees/tracking differences, not the gross TR benchmark.                                                             https://www.invesco.com/qqq-etf/en/home.html
```

## fx-validation

```text
            USD value    EURUSD  Computed EUR value
Date
2003-12-01   0.324669  1.196501            0.271349
2003-12-02   0.322127  1.208897            0.266463
2003-12-03   0.314500  1.212298            0.259425
2003-12-04   0.316295  1.208094            0.261813
2003-12-05   0.311807  1.218695            0.255854
```

## asset-performance

```text
                   CAGR  Mean return annualized  Volatility annualized  Max Drawdown    Sharpe    Calmar
Asset
Apple x1.5     0.642909                0.655551               0.543697     -0.759786  1.205729  0.846171
Apple          0.440246                0.443106               0.374333     -0.565253  1.183721  0.778847
Gold           0.093070                0.113356               0.211527     -0.373896  0.535894  0.248921
Nasdaq 100     0.115152                0.139345               0.236260     -0.468036  0.589797  0.246032
Nasdaq 100 x2  0.181751                0.260737               0.423958     -0.791747  0.615007  0.229557
Dow Jones      0.080493                0.101161               0.209625     -0.466981  0.482581  0.172369
S&P 500        0.084311                0.106731               0.218681     -0.512942  0.488068  0.164368
CAC 40         0.060170                0.085225               0.225922     -0.570832  0.377231  0.105407
```

## leverage-diagnostics

```text
           Asset  Underlying  Leverage  Reset sessions  Worst underlying return Wipeout date
0     Apple x1.5       Apple       1.5            3035                -0.179195          NaT
1  Nasdaq 100 x2  Nasdaq 100       2.0            3035                -0.089557          NaT
```

## portfolio-results

```text
                        CAGR Mean return annualized Volatility Max Drawdown    Sharpe    Calmar Success Solver status                                Status Risk ceiling                                                Main Allocation
Portfolio
Minimum Volatility   0.09272               0.101281   0.145655    -0.231925  0.695348  0.399784    True             0  Optimization terminated successfully          NaN                    Gold 43.4% · CAC 40 32.5% · Dow Jones 24.1%
Maximum CAGR        0.642909               0.655551   0.543697    -0.759786  1.205729  0.846171    True             0  Optimization terminated successfully          NaN                                              Apple x1.5 100.0%
Maximum Sharpe      0.365763               0.356893   0.276056    -0.419164  1.292828    0.8726    True             0  Optimization terminated successfully          NaN                    Gold 46.8% · Apple x1.5 45.3% · CAC 40 7.9%
Prudent             0.123288               0.130137       0.15    -0.246124  0.867583  0.500919    True             0  Optimization terminated successfully         0.15  Gold 45.4% · CAC 40 31.4% · Dow Jones 18.1% · Apple x1.5 5.1%
Modéré              0.250146               0.248329        0.2    -0.319281  1.241644  0.783469    True             0  Optimization terminated successfully          0.2                   Gold 49.4% · Apple x1.5 26.2% · CAC 40 24.4%
Dynamique           0.397562               0.387322        0.3    -0.447148  1.291075  0.889107    True             0  Optimization terminated successfully          0.3                    Apple x1.5 50.7% · Gold 46.1% · CAC 40 3.2%
Agressif            0.513955               0.504116        0.4    -0.586412  1.260291  0.876441    True             0  Optimization terminated successfully          0.4                                  Apple x1.5 72.1% · Gold 27.9%
Très agressif       0.607666               0.610546        0.5    -0.715315  1.221092  0.849508    True             0  Optimization terminated successfully          0.5                                   Apple x1.5 91.7% · Gold 8.3%
```

## portfolio-weights

```text
                   Apple x1.5 Nasdaq 100 x2 S&P 500 Dow Jones  CAC 40    Gold
Portfolio
Minimum Volatility      0.00%         0.00%   0.00%    24.15%  32.46%  43.40%
Maximum CAGR          100.00%         0.00%   0.00%     0.00%   0.00%   0.00%
Maximum Sharpe         45.33%         0.00%   0.00%     0.00%   7.88%  46.80%
Prudent                 5.13%         0.00%   0.00%    18.06%  31.43%  45.38%
Modéré                 26.16%         0.00%   0.00%     0.00%  24.42%  49.42%
Dynamique              50.70%         0.00%   0.00%     0.00%   3.21%  46.09%
Agressif               72.07%         0.00%   0.00%     0.00%   0.00%  27.93%
Très agressif          91.70%         0.00%   0.00%     0.00%   0.00%   8.30%
```

## covariance

```text
               Apple x1.5  Nasdaq 100 x2   S&P 500  Dow Jones    CAC 40      Gold
Apple x1.5       0.295606       0.157647  0.067602   0.059760  0.032271  0.007375
Nasdaq 100 x2    0.157647       0.179740  0.082270   0.074850  0.048541  0.006357
S&P 500          0.067602       0.082270  0.047821   0.044648  0.023215  0.009002
Dow Jones        0.059760       0.074850  0.044648   0.043943  0.020983  0.008742
CAC 40           0.032271       0.048541  0.023215   0.020983  0.051041 -0.000962
Gold             0.007375       0.006357  0.009002   0.008742 -0.000962  0.044744
```

## frontier-dominance

```text
               100% CAGR  100% volatility  Frontier CAGR  Frontier volatility
Asset
Apple x1.5      0.642909         0.543697       0.642909             0.543697
Nasdaq 100 x2   0.181751         0.423958       0.538159             0.423958
S&P 500         0.084311         0.218681       0.281786             0.218681
Dow Jones       0.080493         0.209625       0.266867             0.209625
CAC 40          0.060170         0.225922       0.293269             0.225922
Gold            0.093070         0.211527       0.270059             0.211527
```

## solver-log

```text
                  Portfolio  Success  Status                                         Message  Iterations          ftol  Raw minimum weight  Raw weight sum
0        Minimum Volatility     True       0            Optimization terminated successfully          13  1.000000e-10        0.000000e+00             1.0
1              Maximum CAGR     True       0            Optimization terminated successfully           3  1.000000e-10        0.000000e+00             1.0
2    Maximum Sharpe start 0     True       0            Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
3    Maximum Sharpe start 1     True       0            Optimization terminated successfully          12  1.000000e-10        0.000000e+00             1.0
4    Maximum Sharpe start 2     True       0            Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
5    Maximum Sharpe start 3     True       0            Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
6    Maximum Sharpe start 4     True       0            Optimization terminated successfully          11  1.000000e-10        0.000000e+00             1.0
7    Maximum Sharpe start 5     True       0            Optimization terminated successfully          11  1.000000e-10        0.000000e+00             1.0
8    Maximum Sharpe start 6     True       0            Optimization terminated successfully          11  1.000000e-10        0.000000e+00             1.0
9    Maximum Sharpe start 7     True       0            Optimization terminated successfully          13  1.000000e-10        6.630574e-18             1.0
10   Maximum Sharpe start 8     True       0            Optimization terminated successfully          12  1.000000e-10        0.000000e+00             1.0
11               Frontier 1     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
12               Frontier 2     True       0            Optimization terminated successfully          10  1.000000e-10        2.109776e-17             1.0
13               Frontier 3     True       0            Optimization terminated successfully          10  1.000000e-10        0.000000e+00             1.0
14               Frontier 4     True       0            Optimization terminated successfully          11  1.000000e-10        0.000000e+00             1.0
15               Frontier 5     True       0            Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
16               Frontier 6     True       0            Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
17               Frontier 7     True       0            Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
18               Frontier 8     True       0            Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
19               Frontier 9     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
20              Frontier 10     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
21              Frontier 11     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
22              Frontier 12     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
23              Frontier 13     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
24              Frontier 14     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
25              Frontier 15     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
26              Frontier 16     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
27              Frontier 17     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
28              Frontier 18     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
29              Frontier 19     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
30              Frontier 20     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
31              Frontier 21     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
32              Frontier 22     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
33              Frontier 23     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
34              Frontier 24     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
35              Frontier 25     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
36              Frontier 26     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
37              Frontier 27     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
38              Frontier 28     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
39              Frontier 29     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
40              Frontier 30     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
41              Frontier 31     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
42              Frontier 32     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
43              Frontier 33     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
44              Frontier 34     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
45              Frontier 35     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
46              Frontier 36     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
47              Frontier 37     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
48              Frontier 38     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
49              Frontier 39     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
50              Frontier 40     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
51              Frontier 41     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
52              Frontier 42     True       0            Optimization terminated successfully          23  1.000000e-10        5.612019e-19             1.0
53              Frontier 43     True       0            Optimization terminated successfully          19  1.000000e-10        3.635953e-18             1.0
54              Frontier 44     True       0            Optimization terminated successfully           6  1.000000e-10        0.000000e+00             1.0
55              Frontier 45     True       0            Optimization terminated successfully           6  1.000000e-10        0.000000e+00             1.0
56              Frontier 46     True       0            Optimization terminated successfully           6  1.000000e-10        0.000000e+00             1.0
57              Frontier 47     True       0            Optimization terminated successfully           6  1.000000e-10        0.000000e+00             1.0
58              Frontier 48    False       8  Positive directional derivative for linesearch          35  1.000000e-10        2.973660e-19             1.0
59              Frontier 48     True       0            Optimization terminated successfully           1  1.000000e-07        2.973660e-19             1.0
60                  Prudent     True       0            Optimization terminated successfully           8  1.000000e-10        1.217136e-18             1.0
61                   Modéré     True       0            Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
62                Dynamique     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
63                 Agressif     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
64            Très agressif     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
65  Dominance Nasdaq 100 x2     True       0            Optimization terminated successfully           7  1.000000e-10        0.000000e+00             1.0
66        Dominance S&P 500     True       0            Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
67      Dominance Dow Jones     True       0            Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
68         Dominance CAC 40     True       0            Optimization terminated successfully           9  1.000000e-10        0.000000e+00             1.0
69           Dominance Gold     True       0            Optimization terminated successfully           8  1.000000e-10        0.000000e+00             1.0
```

## frontier

```text
        CAGR  Mean return annualized  Volatility  Max Drawdown    Sharpe    Calmar  Success  Solver status                                       Status  Risk ceiling Weight: Apple x1.5 Weight: Nasdaq 100 x2 Weight: S&P 500 Weight: Dow Jones Weight: CAC 40 Weight: Gold
0   0.092720                0.101281    0.145655     -0.231925  0.695348  0.399784     True              0                Minimum achievable volatility      0.145655              0.00%                 0.00%           0.00%            24.15%         32.46%       43.40%
1   0.139559                0.145419    0.153778     -0.255043  0.945641  0.547199     True              0         Optimization terminated successfully      0.153778              7.86%                 0.00%           0.00%            14.75%         31.12%       46.28%
2   0.166198                0.170335    0.161901     -0.269878  1.052093  0.615828     True              0         Optimization terminated successfully      0.161901             12.31%                 0.00%           0.00%             9.34%         30.61%       47.74%
3   0.187788                0.190446    0.170025     -0.282099  1.120109  0.665681     True              0         Optimization terminated successfully      0.170025             15.90%                 0.00%           0.00%             4.98%         30.21%       48.92%
4   0.206798                0.208101    0.178148     -0.292995  1.168133  0.705805     True              0         Optimization terminated successfully      0.178148             19.05%                 0.00%           0.00%             1.15%         29.85%       49.95%
5   0.224080                0.224125    0.186271     -0.303229  1.203220  0.738981     True              0         Optimization terminated successfully      0.186271             21.89%                 0.00%           0.00%             0.00%         28.10%       50.01%
6   0.239880                0.238789    0.194395     -0.312890  1.228372  0.766660     True              0         Optimization terminated successfully      0.194395             24.48%                 0.00%           0.00%             0.00%         25.87%       49.65%
7   0.254621                0.252490    0.202518     -0.322094  1.246755  0.790519     True              0         Optimization terminated successfully      0.202518             26.90%                 0.00%           0.00%             0.00%         23.78%       49.32%
8   0.268577                0.265483    0.210641     -0.330971  1.260354  0.811481     True              0         Optimization terminated successfully      0.210641             29.19%                 0.00%           0.00%             0.00%         21.80%       49.01%
9   0.281921                0.277929    0.218765     -0.341823  1.270450  0.824757     True              0         Optimization terminated successfully      0.218765             31.39%                 0.00%           0.00%             0.00%         19.90%       48.71%
10  0.294775                0.289944    0.226888     -0.354071  1.277916  0.832531     True              0         Optimization terminated successfully      0.226888             33.51%                 0.00%           0.00%             0.00%         18.07%       48.42%
11  0.307224                0.301606    0.235011     -0.365797  1.283370  0.839876     True              0         Optimization terminated successfully      0.235011             35.57%                 0.00%           0.00%             0.00%         16.29%       48.14%
12  0.319332                0.312977    0.243134     -0.377075  1.287261  0.846865     True              0         Optimization terminated successfully      0.243134             37.57%                 0.00%           0.00%             0.00%         14.56%       47.87%
13  0.331148                0.324104    0.251258     -0.387965  1.289925  0.853550     True              0         Optimization terminated successfully      0.251258             39.54%                 0.00%           0.00%             0.00%         12.86%       47.60%
14  0.342709                0.335021    0.259381     -0.398511  1.291617  0.859973     True              0         Optimization terminated successfully      0.259381             41.46%                 0.00%           0.00%             0.00%         11.19%       47.34%
15  0.354045                0.345758    0.267504     -0.408749  1.292533  0.866167     True              0         Optimization terminated successfully      0.267504             43.36%                 0.00%           0.00%             0.00%          9.56%       47.09%
16  0.365180                0.356339    0.275628     -0.418709  1.292827  0.872157     True              0         Optimization terminated successfully      0.275628             45.23%                 0.00%           0.00%             0.00%          7.94%       46.83%
17  0.376134                0.366782    0.283751     -0.428416  1.292621  0.877966     True              0         Optimization terminated successfully      0.283751             47.07%                 0.00%           0.00%             0.00%          6.35%       46.58%
18  0.386923                0.377105    0.291874     -0.437889  1.292011  0.883611     True              0         Optimization terminated successfully      0.291874             48.89%                 0.00%           0.00%             0.00%          4.77%       46.34%
19  0.397559                0.387319    0.299998     -0.447145  1.291075  0.889106     True              0         Optimization terminated successfully      0.299998             50.70%                 0.00%           0.00%             0.00%          3.21%       46.09%
20  0.408054                0.397438    0.308121     -0.456200  1.289876  0.894464     True              0         Optimization terminated successfully      0.308121             52.48%                 0.00%           0.00%             0.00%          1.67%       45.85%
21  0.418417                0.407470    0.316244     -0.465066  1.288466  0.899695     True              0         Optimization terminated successfully      0.316244             54.25%                 0.00%           0.00%             0.00%          0.13%       45.61%
22  0.428602                0.417388    0.324367     -0.470248  1.286775  0.911439     True              0         Optimization terminated successfully      0.324367             56.07%                 0.00%           0.00%             0.00%          0.00%       43.93%
23  0.438552                0.427152    0.332491     -0.482207  1.284705  0.909468     True              0         Optimization terminated successfully      0.332491             57.88%                 0.00%           0.00%             0.00%          0.00%       42.12%
24  0.448283                0.436780    0.340614     -0.495213  1.282332  0.905232     True              0         Optimization terminated successfully      0.340614             59.65%                 0.00%           0.00%             0.00%          0.00%       40.35%
25  0.457812                0.446286    0.348737     -0.507829  1.279718  0.901508     True              0         Optimization terminated successfully      0.348737             61.40%                 0.00%           0.00%             0.00%          0.00%       38.60%
26  0.467151                0.455681    0.356861     -0.520274  1.276916  0.897894     True              0         Optimization terminated successfully      0.356861             63.14%                 0.00%           0.00%             0.00%          0.00%       36.86%
27  0.476312                0.464977    0.364984     -0.533081  1.273967  0.893508     True              0         Optimization terminated successfully      0.364984             64.85%                 0.00%           0.00%             0.00%          0.00%       35.15%
28  0.485303                0.474184    0.373107     -0.545553  1.270905  0.889562     True              0         Optimization terminated successfully      0.373107             66.55%                 0.00%           0.00%             0.00%          0.00%       33.45%
29  0.494133                0.483309    0.381231     -0.557707  1.267760  0.886008     True              0         Optimization terminated successfully      0.381231             68.23%                 0.00%           0.00%             0.00%          0.00%       31.77%
30  0.502809                0.492359    0.389354     -0.570022  1.264553  0.882088     True              0         Optimization terminated successfully      0.389354             69.90%                 0.00%           0.00%             0.00%          0.00%       30.10%
31  0.511336                0.501340    0.397477     -0.582581  1.261305  0.877708     True              0         Optimization terminated successfully      0.397477             71.56%                 0.00%           0.00%             0.00%          0.00%       28.44%
32  0.519720                0.510258    0.405600     -0.594800  1.258032  0.873773     True              0         Optimization terminated successfully      0.405600             73.20%                 0.00%           0.00%             0.00%          0.00%       26.80%
33  0.527964                0.519119    0.413724     -0.606691  1.254747  0.870236     True              0         Optimization terminated successfully      0.413724             74.84%                 0.00%           0.00%             0.00%          0.00%       25.16%
34  0.536074                0.527925    0.421847     -0.618267  1.251462  0.867059     True              0         Optimization terminated successfully      0.421847             76.46%                 0.00%           0.00%             0.00%          0.00%       23.54%
35  0.544051                0.536682    0.429970     -0.629537  1.248184  0.864208     True              0         Optimization terminated successfully      0.429970             78.08%                 0.00%           0.00%             0.00%          0.00%       21.92%
36  0.551899                0.545393    0.438094     -0.640512  1.244923  0.861652     True              0         Optimization terminated successfully      0.438094             79.68%                 0.00%           0.00%             0.00%          0.00%       20.32%
37  0.559620                0.554060    0.446217     -0.651201  1.241684  0.859365     True              0         Optimization terminated successfully      0.446217             81.28%                 0.00%           0.00%             0.00%          0.00%       18.72%
38  0.567216                0.562688    0.454340     -0.661612  1.238472  0.857324     True              0         Optimization terminated successfully      0.454340             82.87%                 0.00%           0.00%             0.00%          0.00%       17.13%
39  0.574689                0.571278    0.462464     -0.671754  1.235292  0.855506     True              0         Optimization terminated successfully      0.462464             84.46%                 0.00%           0.00%             0.00%          0.00%       15.54%
40  0.582042                0.579832    0.470587     -0.681633  1.232147  0.853893     True              0         Optimization terminated successfully      0.470587             86.03%                 0.00%           0.00%             0.00%          0.00%       13.97%
41  0.589274                0.588354    0.478710     -0.691256  1.229040  0.852467     True              0         Optimization terminated successfully      0.478710             87.61%                 0.00%           0.00%             0.00%          0.00%       12.39%
42  0.596387                0.596845    0.486833     -0.700632  1.225973  0.851213     True              0         Optimization terminated successfully      0.486833             89.17%                 0.00%           0.00%             0.00%          0.00%       10.83%
43  0.603382                0.605306    0.494957     -0.709764  1.222948  0.850116     True              0         Optimization terminated successfully      0.494957             90.73%                 0.00%           0.00%             0.00%          0.00%        9.27%
44  0.610260                0.613741    0.503080     -0.718660  1.219966  0.849163     True              0         Optimization terminated successfully      0.503080             92.29%                 0.00%           0.00%             0.00%          0.00%        7.71%
45  0.617021                0.622149    0.511203     -0.727326  1.217028  0.848342     True              0         Optimization terminated successfully      0.511203             93.84%                 0.00%           0.00%             0.00%          0.00%        6.16%
46  0.623666                0.630533    0.519327     -0.735766  1.214135  0.847642     True              0         Optimization terminated successfully      0.519327             95.39%                 0.00%           0.00%             0.00%          0.00%        4.61%
47  0.630196                0.638894    0.527450     -0.743986  1.211288  0.847053     True              0         Optimization terminated successfully      0.527450             96.93%                 0.00%           0.00%             0.00%          0.00%        3.07%
48  0.636610                0.647232    0.535573     -0.751991  1.208486  0.846566     True              0         Optimization terminated successfully      0.535573             98.47%                 0.00%           0.00%             0.00%          0.00%        1.53%
49  0.642909                0.655551    0.543697     -0.759786  1.205729  0.846171     True              0  Maximum CAGR reached; unused risk allowance      0.543697            100.00%                 0.00%           0.00%             0.00%          0.00%        0.00%
```

## Numerical sanity checks

```json
{
  "portfolio_weight_sums": {
    "Minimum Volatility": 1.0,
    "Maximum CAGR": 1.0,
    "Maximum Sharpe": 0.9999999999999998,
    "Prudent": 1.0,
    "Mod\u00e9r\u00e9": 1.0,
    "Dynamique": 1.0,
    "Agressif": 1.0,
    "Tr\u00e8s agressif": 1.0,
    "Frontier 0": 1.0,
    "Frontier 1": 1.0,
    "Frontier 2": 1.0000000000000002,
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
    "Frontier 18": 0.9999999999999999,
    "Frontier 19": 1.0,
    "Frontier 20": 1.0,
    "Frontier 21": 1.0,
    "Frontier 22": 1.0,
    "Frontier 23": 1.0,
    "Frontier 24": 1.0,
    "Frontier 25": 1.0,
    "Frontier 26": 1.0,
    "Frontier 27": 1.0,
    "Frontier 28": 0.9999999999999998,
    "Frontier 29": 0.9999999999999999,
    "Frontier 30": 1.0,
    "Frontier 31": 1.0,
    "Frontier 32": 1.0,
    "Frontier 33": 1.0,
    "Frontier 34": 1.0,
    "Frontier 35": 0.9999999999999999,
    "Frontier 36": 1.0,
    "Frontier 37": 1.0,
    "Frontier 38": 1.0,
    "Frontier 39": 1.0,
    "Frontier 40": 1.0,
    "Frontier 41": 1.0,
    "Frontier 42": 1.0,
    "Frontier 43": 1.0,
    "Frontier 44": 1.0,
    "Frontier 45": 1.0,
    "Frontier 46": 0.9999999999999999,
    "Frontier 47": 0.9999999999999999,
    "Frontier 48": 0.9999999999999999,
    "Frontier 49": 1.0
  },
  "minimum_portfolio_weight": 0.0,
  "maximum_weight_sum_error": 2.220446049250313e-16,
  "largest_volatility_ceiling_violation": 4.5522753344684475e-09,
  "nonfinite_final_returns": 0,
  "common_observations": 2970,
  "return_observations": 2969,
  "common_start": "2003-12-01",
  "common_end": "2015-12-18",
  "covariance_minimum_eigenvalue": 0.0009843410428964077,
  "solver_attempts": 70,
  "successful_solver_attempts": 69,
  "optimizer_solve_count": 69,
  "optimizer_success_count": 69,
  "unsuccessful_solver_attempts": 1
}
```

## Historical coverage

```json
{
  "common_start": "2003-12-01",
  "common_end": "2015-12-18",
  "common_observations": 2970,
  "latest_raw_asset_start": "2000-08-30",
  "raw_start_limiting_assets": [
    "Gold"
  ],
  "earliest_raw_asset_end": "2015-12-18",
  "raw_end_limiting_assets": [
    "CAC 40"
  ],
  "latest_eur_asset_start": "2003-12-01",
  "eur_start_limiting_assets": [
    "Apple",
    "Nasdaq 100",
    "S&P 500",
    "Dow Jones",
    "Gold"
  ],
  "start_limiting_series": [
    "EURUSD=X"
  ],
  "fx_start": "2003-12-01",
  "first_common_date_delayed_by_calendar": false
}
```