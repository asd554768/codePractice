// The API isBadVersion is defined for you.
// bool isBadVersion(int version);

class Solution {
public:

    int firstBadVersion(int n) {
        long long front=0;
        long long rear=n;
        long long mid=(front+rear)/2;
        
        while(front!=rear){
            
            if(isBadVersion(mid)){
                rear=mid;
                mid=(front+rear)/2;
            }else{
                front=mid+1;
                mid=(front+rear)/2;
            }
        }
        //cout<<front<<" "<<mid<<" "<<rear<<endl;
        return front;
    }
};