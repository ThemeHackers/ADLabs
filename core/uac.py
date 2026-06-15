import sys
import argparse
import samba
from samba.samdb import SamDB
import samba.param
import traceback
from ldb import Message, MessageElement, FLAG_MOD_REPLACE, Dn

def main():
    print("Script started", flush=True)
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', required=True)
    parser.add_argument('--uac', required=True)
    args = parser.parse_args()
    print(f"Args: username={args.username}, uac={args.uac}", flush=True)

    try:
        print("Loading samdb...", flush=True)
        lp = samba.param.LoadParm()
        lp.load('/samba/etc/smb.conf')
        samdb = SamDB(url='/samba/private/sam.ldb', lp=lp)
        print("SamDB loaded", flush=True)

        root_dn = str(samdb.domain_dn())
        print(f"Root DN: {root_dn}", flush=True)
        user_dn = f"CN={args.username},CN=Users,{root_dn}"
        print(f"User DN: {user_dn}", flush=True)

        m = Message()
        m.dn = Dn(samdb, user_dn)
        print("Message object created", flush=True)
        
        m["userAccountControl"] = MessageElement(str(args.uac), FLAG_MOD_REPLACE, "userAccountControl")
        print("MessageElement added", flush=True)
        
        print("Modifying database...", flush=True)
        samdb.modify(m)
        print(f"Successfully modified userAccountControl for {args.username} to {args.uac} on {root_dn}", flush=True)
    except Exception as e:
        print("ERROR occurred inside python script:", flush=True)
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        sys.exit(1)

if __name__ == '__main__':
    main()
