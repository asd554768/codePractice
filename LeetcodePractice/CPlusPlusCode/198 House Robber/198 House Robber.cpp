class Solution {
public:
    int recursive(vector<int>& dp,vector<int>& nums,int i){
        if(i<0) return 0;
        if(dp[i]>=0) return dp[i];
        int result= max((recursive(dp,nums,i-2)+nums[i]),recursive(dp,nums,i-1));
        //max(搶前兩間時所獲的錢之總和+搶這一間的錢,不搶這一間錢之總和)
        dp[i]=result;
        return result;
    }
    int rob(vector<int>& nums) {
        int len=nums.size();
        if(len==1) return nums.back();
        vector <int> dp(nums.size()+1,-1);
        return recursive(dp,nums,len-1);
        
    }
};