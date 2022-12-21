class Solution {
public:
    
    
    vector<vector<int>> generate(int numRows) {
        vector<vector<int>> dp;
        for(int i=0;i<numRows;i++){
            dp.push_back(vector<int>(i+1,1));
            for(int j=1;j<i;j++){
                
                dp[i][j]=dp[i-1][j]+dp[i-1][j-1];
                cout<<"i:"<<i<<" j: "<<j<<" "<<dp[i][j]<<endl;
            }
        }
        return dp;
    }
};