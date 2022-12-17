class Solution {
public:
    int mySqrt(int x) {
        if(x==1 || x==0)
            return x;
        if(x==2 || x==3)
            return 1;
        else{
            long long low=2,high=x/2,mid,ans;
            while(low<=high){
                mid=low+(high-low)/2;
                if(mid * mid == x)
                    return mid;
                else if(mid * mid < x){
                    ans=mid;
                    low=mid+1;
                }    
                else
                    high=mid-1;    
            }
            return ans;  
        }
    }
};