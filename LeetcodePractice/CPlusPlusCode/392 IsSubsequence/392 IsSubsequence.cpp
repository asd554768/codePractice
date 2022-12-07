class Solution {
public:
    bool isSubsequence(string s, string t) {
        int index=0;
        string tempStr=t;
        for(int i=0;i<s.size();i++){
            char temp =s[i];
            tempStr=tempStr.substr(index);
            //cout<<index<<" "<<temp<<" "<<tempStr<<endl;
            index=tempStr.find(temp);
            if(index==tempStr.npos){
                return false;
            } 
            index++;
        }
        return true;
    }
};