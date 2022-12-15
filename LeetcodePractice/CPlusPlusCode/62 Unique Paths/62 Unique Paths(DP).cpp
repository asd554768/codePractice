class Solution {
public:
    int uniquePaths(int m, int n) {
        vector<vector<int>> dp(m,vector<int>(n,1));//表示至少一條
        for(int i=1;i<m;i++){
            for(int j=1;j<n;j++){
                dp[i][j]=dp[i][j-1]+dp[i-1][j];
                //將前一步驟從左邊來的所有可能加上所有步驟從上面來的可能相加
            }
        }
        return dp[m-1][n-1];
        
    }
};