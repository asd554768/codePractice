bool isValid(char * s){
    int length = strlen(s);
    char *right = (char *) malloc(length * sizeof(char));
    int x = -1;
    for(int i = 0; i < length; i++) {
        if(s[i] == '(') right[++x] = ')';
        else if(s[i] == '{') right[++x] = '}';
        else if(s[i] == '[') right[++x] = ']';
        else {
            if(x >= 0 && s[i] == right[x]) x--;
            else return false;
        }
    }
    if(x == -1) return true;
    else return false;
}