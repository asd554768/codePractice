# 解說(mid)

## LCS標準題

* 將兩序列拆成三種方式來觀看
S1=sub1+e1
S2=sub2+e2
1. 當兩字皆相同時，表示一定含有這個字，所以S1和S2可以表示成substr+1，LCS(sub1,sub2)+1
2. LCS 包含 e1 但不含 e2。 此種情形對於 e2 沒有用處，若要找到 LCS 只需找 sub2 即可。LCS(S1,sub2)
3. LCS 包含 e2 但不含 e1。 此種情形對於 e1 沒有用處，若要找到 LCS 只需找 sub1 即可。LCS(sub1,S2)

![](https://i.imgur.com/p0y9Tu7.png)
![](https://i.imgur.com/3egSKUD.png)
## Reference
### [參考解說](https://yungshenglu.github.io/2018/05/15/LongestCommonSubsequence1/)
### [參考影片](https://www.youtube.com/watch?v=rHV2MT2tD7Y)