class Solution {
public:
    bool isIsomorphic(string s, string t) {
        unordered_map <char,char> um;
        set<char> sc;        

        if(s.size()!=t.size()) return false;
        //cout<<"test"<<endl;
        for(int i=0 ;i<s.size();i++){
            if(um.find(s[i])==um.end()){
                if(sc.find(t[i])!=sc.end()) return false;
                um[s[i]]=t[i];
                sc.insert(t[i]);

            }else if(um[s[i]]!=t[i]){
                return false;
            }
        }
        return true;

    }
};