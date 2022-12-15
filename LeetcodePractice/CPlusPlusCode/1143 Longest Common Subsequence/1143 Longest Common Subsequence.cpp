class Solution {
public:
    int longestCommonSubsequence(string text1, string text2) {
        vector<vector<int>> dp(1001,vector<int>(1001,0));
        //cout<<"hello"<<dp[0][0]<<endl;
        for(int i=0;i<text1.size();i++){
            for(int j=0;j<text2.size();j++){
                dp[i+1][j+1]=(text1[i]==text2[j])?dp[i][j]+1:max(dp[i][j+1],dp[i+1][j]);
            }
        }
        return dp[text1.size()][text2.size()];
    }
};