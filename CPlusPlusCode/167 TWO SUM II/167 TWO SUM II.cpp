class Solution {
public:
    vector<int> twoSum(vector<int>& numbers, int target) {
        
        int pos=0;
        int nes=numbers.size()-1;
        int total;
        while(pos<nes){
            total=numbers[pos]+numbers[nes];
            if(total==target) return vector<int> {pos+1,nes+1};
            if(total>target) nes--;
            else pos++;
        }       
        return vector<int> {pos+1,nes+1};
    }
};