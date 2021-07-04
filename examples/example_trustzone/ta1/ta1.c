#include <inttypes.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#include <tee_internal_api.h>

#include <ta1.h>
#include <pta_attestation.h>
#include <spongent.h>

static const TEE_UUID pta_attestation_uuid = ATTESTATION_UUID;

void *malloc_aligned(size_t size) {
  size += size % 2;

  return malloc(size);
}

int total_node = 0;

typedef struct
{
    uint8_t  encryption;
	uint16_t conn_id;
    uint16_t io_id;
    uint16_t nonce;
    unsigned char connection_key[16];
} Connection;

typedef struct Node
{
    Connection connection;
    struct Node* next;
} Node;

static Node* connections_head = NULL;

int connections_add(Connection* connection)
{
   Node* node = malloc_aligned(sizeof(Node));

   if (node == NULL)
      return 0;

   printf("@@@@@@@@ inside add_connection @@@@@@\n");
   for (int j = 0; j < 16; j++){
	   printf("%02X", connection->connection_key[j]);
   }

   node->connection = *connection;
   node->next = connections_head;
   connections_head = node;
   return 1;
}

Connection* connections_get(uint16_t conn_id)
{
	printf("$$$$$$$$ inside of get_connections func $$$$$$$\n");
    Node* current = connections_head;

    while (current != NULL) {
        Connection* connection = &current->connection;

        if (connection->conn_id == conn_id) {
			for (int j = 0; j < 16; j++)
		   		printf("%02X", connection->connection_key[j]);
            return connection;
        }

        current = current->next;
    }

    return NULL;
}

void find_connections(uint16_t io_id, int *arr, uint8_t *num)
{
	printf("%%%%%%%%%%%% inside of find_connections func %%%%%%%%%\n");
    Node* current = connections_head;

    while (current != NULL) {
        Connection* connection = &current->connection;

        if (connection->io_id == io_id) {
            arr[*num] = connection->conn_id;
			printf("conn_id %d\n", arr[*num]);
            *num = *num + 1;
        }

        current = current->next;
    }

}

//===============================================================

char module_key[16] = { 0 };

struct aes_cipher {
	uint32_t algo;			/* AES flavour */
	uint32_t mode;			/* Encode or decode */
	uint32_t key_size;		/* AES key size in byte */
	TEE_OperationHandle op_handle;	/* AES ciphering operation */
	TEE_ObjectHandle key_handle;	/* transient object to load the key */
};

//===============================================================

static TEE_Result ta2tee_algo_id(uint32_t param, uint32_t *algo)
{
	switch (param) {
	case TA_AES_ALGO_ECB:
		*algo = TEE_ALG_AES_ECB_NOPAD;
		return TEE_SUCCESS;
	case TA_AES_ALGO_CBC:
		*algo = TEE_ALG_AES_CBC_NOPAD;
		return TEE_SUCCESS;
	case TA_AES_ALGO_GCM:
		*algo = TEE_ALG_AES_GCM;
		return TEE_SUCCESS;
	default:
		EMSG("Invalid algo %u", param);
		return TEE_ERROR_BAD_PARAMETERS;
	}
}
static TEE_Result ta2tee_key_size(uint32_t param, uint32_t *key_size)
{
	switch (param) {
	case 16:
		*key_size = param;
		return TEE_SUCCESS;
	default:
		EMSG("Invalid key size %u", param);
		return TEE_ERROR_BAD_PARAMETERS;
	}
}
static TEE_Result ta2tee_mode_id(uint32_t param, uint32_t *mode)
{
	switch (param) {
	case TA_AES_MODE_ENCODE:
		*mode = TEE_MODE_ENCRYPT;
		return TEE_SUCCESS;
	case TA_AES_MODE_DECODE:
		*mode = TEE_MODE_DECRYPT;
		return TEE_SUCCESS;
	default:
		EMSG("Invalid mode %u", param);
		return TEE_ERROR_BAD_PARAMETERS;
	}
}

static TEE_Result alloc_resources(void *session, uint32_t algo, uint32_t key_size,
                                    uint32_t mode){
	
	struct aes_cipher *sess;
	TEE_Attribute attr;
	TEE_Result res;
	char *key;

	/* Get ciphering context from session ID */
	DMSG("Session %p: get ciphering resources", session);
	sess = (struct aes_cipher *)session;

	res = ta2tee_algo_id(algo, &sess->algo);
	if (res != TEE_SUCCESS)
		return res;

	res = ta2tee_key_size(key_size, &sess->key_size);
	if (res != TEE_SUCCESS)
		return res;

	res = ta2tee_mode_id(mode, &sess->mode);
	if (res != TEE_SUCCESS)
		return res;

	if (sess->op_handle != TEE_HANDLE_NULL)
		TEE_FreeOperation(sess->op_handle);

	/* Allocate operation: AES/CTR, mode and size from params */
	res = TEE_AllocateOperation(&sess->op_handle,
				    sess->algo,
				    sess->mode,
				    sess->key_size * 8);
	if (res != TEE_SUCCESS) {
		EMSG("Failed to allocate operation");
		sess->op_handle = TEE_HANDLE_NULL;
		goto err;
	}

	/* Free potential previous transient object */
	if (sess->key_handle != TEE_HANDLE_NULL)
		TEE_FreeTransientObject(sess->key_handle);

	/* Allocate transient object according to target key size */
	res = TEE_AllocateTransientObject(TEE_TYPE_AES,
					  sess->key_size * 8,
					  &sess->key_handle);
	if (res != TEE_SUCCESS) {
		EMSG("Failed to allocate transient object");
		sess->key_handle = TEE_HANDLE_NULL;
		goto err;
	}

	key = TEE_Malloc(sess->key_size, 0);
	if (!key) {
		res = TEE_ERROR_OUT_OF_MEMORY;
		goto err;
	}

	TEE_InitRefAttribute(&attr, TEE_ATTR_SECRET_VALUE, key, sess->key_size);

	res = TEE_PopulateTransientObject(sess->key_handle, &attr, 1);
	if (res != TEE_SUCCESS) {
		EMSG("TEE_PopulateTransientObject failed, %x", res);
		goto err;
	}

	res = TEE_SetOperationKey(sess->op_handle, sess->key_handle);
	if (res != TEE_SUCCESS) {
		EMSG("TEE_SetOperationKey failed %x", res);
		goto err;
	}

	return res;

err:
	if (sess->op_handle != TEE_HANDLE_NULL)
		TEE_FreeOperation(sess->op_handle);
	sess->op_handle = TEE_HANDLE_NULL;

	if (sess->key_handle != TEE_HANDLE_NULL)
		TEE_FreeTransientObject(sess->key_handle);
	sess->key_handle = TEE_HANDLE_NULL;

	return res;
}

static TEE_Result set_aes_key(void *session, char *key, uint32_t key_sz){

	struct aes_cipher *sess;
	TEE_Attribute attr;
	TEE_Result res;

	/* Get ciphering context from session ID */
	DMSG("Session %p: load key material", session);
	sess = (struct aes_cipher *)session;
	
	//---------------------------------------------------------------
	
	printf("//--------------KEY-----------------------\n");
	for (int j = 0; j < 16; j++)
		printf("%02X", key[j]);


	if (key_sz != sess->key_size) {
		EMSG("Wrong key size %" PRIu32 ", expect %" PRIu32 " bytes",
		     key_sz, sess->key_size);
		return TEE_ERROR_BAD_PARAMETERS;
	}

	TEE_InitRefAttribute(&attr, TEE_ATTR_SECRET_VALUE, key, key_sz);

	TEE_ResetTransientObject(sess->key_handle);
	res = TEE_PopulateTransientObject(sess->key_handle, &attr, 1);
	if (res != TEE_SUCCESS) {
		EMSG("TEE_PopulateTransientObject failed, %x", res);
		return res;
	}

	TEE_ResetOperation(sess->op_handle);
	res = TEE_SetOperationKey(sess->op_handle, sess->key_handle);
	if (res != TEE_SUCCESS) {
		EMSG("TEE_SetOperationKey failed %x", res);
		return res;
	}

	return res;
}

static TEE_Result reset_aes_iv(void *session, char *aad, size_t aad_sz, 
                     char *nonce, size_t nonce_sz){
	
	struct aes_cipher *sess;

	/* Get ciphering context from session ID */
	DMSG("Session %p: reset initial vector", session);
	sess = (struct aes_cipher *)session;

	printf("//--------------aaaaaaaadddddd-----------------------\n");
	for (int j = 0; j < aad_sz; j++)
		printf("%02X", aad[j]);
	printf("\n");
	for (int j = 0; j < nonce_sz; j++)
		printf("%02X", nonce[j]);
	//-------------------------------------------------------------------------------
	printf("$$$$$$$$$$$$ before AEInit $$$$$$$$$$");

	TEE_AEInit(sess->op_handle, nonce, nonce_sz, 16*8/* tag_len in bits */, aad_sz /*aad_len*/,
						16 /*plaintext_len*/);
	printf("*********** after AEInit ************");

	TEE_AEUpdateAAD(sess->op_handle, aad, aad_sz);

	printf("*********** after AEUpdate ************");
	
	return TEE_SUCCESS;
}

static TEE_Result set_key(void *session, uint32_t param_types,
				TEE_Param params[4])
{
	TEE_Result res = TEE_ERROR_OUT_OF_MEMORY;
	const uint32_t exp_param_types = TEE_PARAM_TYPES(TEE_PARAM_TYPE_MEMREF_INPUT,
				TEE_PARAM_TYPE_MEMREF_INPUT,
				TEE_PARAM_TYPE_MEMREF_INPUT,
				TEE_PARAM_TYPE_NONE);
	struct aes_cipher *sess;
    Connection connection;
   
	DMSG("Session %p: cipher buffer", session);
	sess = (struct aes_cipher *)session;
    char nonce[16] = { 0 };
    size_t nonce_sz = 16;

    alloc_resources(sess, TA_AES_ALGO_GCM, 16, TA_AES_MODE_DECODE);
    set_aes_key(sess, module_key, 16);
    //memset(nonce, 0, 16); 
    reset_aes_iv(sess, params[0].memref.buffer, params[0].memref.size, nonce, nonce_sz);

    char *tag;
    tag = params[0].memref.buffer;
    char *temp;
   
    void *decrypted_key = NULL;
    void *tag_void = NULL;

   //=============================================================================== 
    decrypted_key = TEE_Malloc(16, 0);
    tag_void = TEE_Malloc(params[2].memref.size, 0);
	if (!decrypted_key || !tag_void)
		goto out;

	TEE_MemMove(tag_void, params[2].memref.buffer, params[2].memref.size);

	res = TEE_AEDecryptFinal(sess->op_handle, params[1].memref.buffer,
				 params[1].memref.size, decrypted_key, &params[2].memref.size, tag_void,
				 params[2].memref.size);

	if (!res) {
      printf("winnnnnnnnnnnnnnnnnnn\n");
      temp = decrypted_key;
      for (int j = 0; j < 16; j++){
		  connection.connection_key[j]= temp[j];
	  }
	  printf("\n");
	  for (int j = 0; j < 16; j++)
		   printf("%02X", connection.connection_key[j]);
	  printf("\n");

	  connection.nonce = 0;
      
	  connection.encryption = tag[0] & 0xFF;

	  printf("^^^^^^encryption: %d", connection.encryption);
	  
	  int j = 0;
      connection.conn_id = 0;
      for(int n=2; n>=1; --n){
         connection.conn_id = connection.conn_id + (( tag[n] & 0xFF ) << (8*j));
         ++j;
      }
      j = 0;
      connection.io_id = 0;
      for(int n=4; n>=3; --n){
         connection.io_id = connection.io_id + (( tag[n] & 0xFF ) << (8*j));
         ++j;
      }
	  total_node = total_node + 1;
      connections_add(&connection);
    }

out:
	TEE_Free(decrypted_key); 
    TEE_Free(tag_void);

	return res;
}

//======================================================================

static TEE_Result attest(void *session, uint32_t param_types,
				TEE_Param params[4])
{
	TEE_Result res = TEE_ERROR_OUT_OF_MEMORY;
	const uint32_t exp_param_types = TEE_PARAM_TYPES(TEE_PARAM_TYPE_MEMREF_INPUT,
				TEE_PARAM_TYPE_MEMREF_OUTPUT,
				TEE_PARAM_TYPE_NONE,
				TEE_PARAM_TYPE_NONE);
	struct aes_cipher *sess;
   
	DMSG("Session %p: cipher buffer", session);
	sess = (struct aes_cipher *)session;

	// ------------ Call PTA ---------**************************************************
	TEE_TASessionHandle pta_session = TEE_HANDLE_NULL;
	uint32_t ret_origin = 0;
	uint32_t pta_param_types = TEE_PARAM_TYPES( TEE_PARAM_TYPE_MEMREF_OUTPUT,
											TEE_PARAM_TYPE_NONE, TEE_PARAM_TYPE_NONE,
											TEE_PARAM_TYPE_NONE);

	TEE_Param pta_params[TEE_NUM_PARAMS];

	// prepare the parameters for the pta
	pta_params[0].memref.buffer = module_key;
	pta_params[0].memref.size = 16;

	// ------------ Open Session to PTA ---------
	res = TEE_OpenTASession(&pta_attestation_uuid, 0, 0, NULL, &pta_session,
				&ret_origin);
	if (res != TEE_SUCCESS)
		return res;

	// ------------ Invoke command at PTA (get_module key) ---------
	res = TEE_InvokeTACommand(pta_session, 0, ATTESTATION_CMD_GET_MODULE_KEY,
								pta_param_types, pta_params, &ret_origin);
	if (res != TEE_SUCCESS)
		return res;

	// ------------ Close Session to PTA ---------
	TEE_CloseTASession(pta_session);

	//*******************************************************************************
    char nonce[16] = { 0 };
    size_t nonce_sz = 16;
	// challenge =  param[0] --> aad 
    alloc_resources(sess, TA_AES_ALGO_GCM, 16, TA_AES_MODE_ENCODE);
    set_aes_key(sess, module_key, 16);
    reset_aes_iv(sess, params[0].memref.buffer, params[0].memref.size, nonce, nonce_sz);

	unsigned char challenge[16]={0};
	unsigned char mytag[16]= {0};
	memcpy(challenge, params[0].memref.buffer, 16);
	for(int i=0; i<16; i++){
		printf("%02X", challenge[i]);
	}
	const void *text = NULL;
	void *encrypted_text = NULL;
    void *tag = NULL;
	
    text = TEE_Malloc(16, 0);
	encrypted_text = TEE_Malloc(16, 0);
    tag = TEE_Malloc(16, 0);	
	
	res = TEE_AEEncryptFinal(sess->op_handle, text,
				 16, encrypted_text, &params[0].memref.size, tag,
				 &params[0].memref.size);
	
	if (!res) {
    	printf("winnnnnn sepooyyyy\n");
		params[1].memref.size = 16;
		TEE_MemMove(params[1].memref.buffer, tag, params[1].memref.size);
    }
	memcpy(mytag, tag, 16);
	for(int i=0; i<16; i++){
		printf(" my tag %02X", mytag[i]);
	}
	TEE_Free(encrypted_text);
	TEE_Free(text);
	TEE_Free(tag);
	
	return TEE_SUCCESS;

}

//======================================================================

void handle_output(void *session, uint16_t output_id, uint32_t param_types,
					 TEE_Param params[4]){

	const uint32_t exp_param_types = TEE_PARAM_TYPES(TEE_PARAM_TYPE_VALUE_INOUT,
				TEE_PARAM_TYPE_MEMREF_OUTPUT,
				TEE_PARAM_TYPE_MEMREF_INOUT,
				TEE_PARAM_TYPE_MEMREF_OUTPUT);

	printf("^^^^^^^^^^^^^inside handle_output fun^^^^^^^^^^^^^\n");
	struct aes_cipher *sess;
	sess = (struct aes_cipher *)session;

	uint32_t data_len = params[0].value.a;
	printf("#### data length: %d\n", data_len);
	uint8_t num = 0;
	void *conn_id_buf;
	void *encrypt_buf;
	void *tag_buf;
	
	//printf("toral node = %d\n", total_node);
	int arr[total_node];
	find_connections(output_id, arr, &num);
	printf("num : %d , connection conn_id %d\n", num, arr[0]);
	params[0].value.a = num;
	printf("param value: %d\n", params[0].value.a);
	conn_id_buf = TEE_Malloc(num * 2, 0);
	encrypt_buf = TEE_Malloc(num * data_len, 0);
	tag_buf = TEE_Malloc(num * 16, 0);

	for(int i=0; i<num; i++){

		Connection* connection = connections_get(arr[i]);
		char nonce[16] = { 0 };
    	size_t nonce_sz = 16;

		unsigned char aad[2] = { 0 };
		int j = 1;
    	for(int m = 0; m < 2; m++){
    		aad[m] = ((connection->nonce) >> (8*j)) & 0xFF; // ########
    		//printf("aad[%d] array: %2X\n", m, aad[m]);
    		j--;
    	}

		unsigned char conn_id_array[2] = { 0 };
		int c = 1;
    	for(int m = 0; m < 2; m++){
    		conn_id_array[m] = ((connection->conn_id) >> (8*j)) & 0xFF; // ########
    		c--;
    	}
		memcpy(conn_id_buf+(2*i), conn_id_array, 2);

		//*************** ^ ^ *******************************************************

		if(connection->encryption == AES){ 

			printf("++++++++++++++I'm inside of AES if+++++++++++\n");

    		alloc_resources(sess, TA_AES_ALGO_GCM, 16, TA_AES_MODE_ENCODE);
    		set_aes_key(sess, connection->connection_key, 16); //#######
    		reset_aes_iv(sess, aad, 2, nonce, nonce_sz);

			void *encrypt = NULL;
			void *tag = NULL;
			uint32_t sz = 16;

			encrypt = TEE_Malloc(data_len, 0);
			tag = TEE_Malloc(16, 0);
    
    		const void *text = NULL;
			text = TEE_Malloc(data_len, 0);
			memcpy(text, params[2].memref.buffer, data_len);

			for(int y=0; y < data_len; y++){
				printf("%02X", ((uint8_t *)text)[y]);
			}

			TEE_Result res = TEE_AEEncryptFinal(sess->op_handle, text, data_len, 
					encrypt, &data_len, tag, &sz);
	
			if (!res) {
				printf("^^^^^winnnnnnnn^^^^^^\n");
				memcpy(encrypt_buf + (data_len * i), encrypt, data_len);
				memcpy(tag_buf + (16*i), tag, 16);
				TEE_Free(encrypt); 
    			TEE_Free(tag);
				TEE_Free(text);
			}
		}
		else {
			//SPONGENT for Sancus
	
			BitSequence output[16]; // output length is the same as the input (in this case, 4 bytes)
			BitSequence tag_spongent[16]; 	// TAG length is the same as the key length. 16 bytes.
			BitSequence data[data_len];
			memcpy(data, params[2].memref.buffer, data_len);

			SpongentWrap(connection->connection_key, aad, 16, data, 128, output, tag_spongent, 0);

			memcpy(encrypt_buf + (data_len * i), output, data_len);
			memcpy(tag_buf + (16*i), tag_spongent, 16);
		}

		connection->nonce = connection->nonce + 1; //######

    } // for
	
	params[1].memref.size = 2*num;
	TEE_MemMove(params[1].memref.buffer, conn_id_buf, params[1].memref.size);
	params[2].memref.size = data_len * num;
	TEE_MemMove(params[2].memref.buffer, encrypt_buf, params[2].memref.size);
	params[3].memref.size = 16*num;
	TEE_MemMove(params[3].memref.buffer, tag_buf, params[3].memref.size);
	
	printf("encryp buf\n");
	for (int n = 0; n<params[2].memref.size; n++)
		printf("%02x ", ((uint8_t *)params[2].memref.buffer)[n]);

	TEE_Free(conn_id_buf);
	TEE_Free(encrypt_buf);
	TEE_Free(tag_buf);
}

void output(void *session, /*unsigned char *data,*/ uint32_t param_types, TEE_Param params[4]){

	const uint32_t exp_param_types = TEE_PARAM_TYPES(TEE_PARAM_TYPE_VALUE_INOUT,
				TEE_PARAM_TYPE_MEMREF_OUTPUT,
				TEE_PARAM_TYPE_MEMREF_INOUT,
				TEE_PARAM_TYPE_MEMREF_OUTPUT);
	printf("^^^^^^^^^^^^^inside output fun^^^^^^^^^^^^^\n");
	struct aes_cipher *sess;
	sess = (struct aes_cipher *)session;
	uint16_t output_id = 0;
	handle_output(sess, output_id, param_types, params);
}

TEE_Result entry(void *session, uint32_t param_types,
			TEE_Param params[4]){

	const uint32_t exp_param_types = TEE_PARAM_TYPES(TEE_PARAM_TYPE_VALUE_INOUT,
				TEE_PARAM_TYPE_MEMREF_OUTPUT,
				TEE_PARAM_TYPE_MEMREF_INOUT,
				TEE_PARAM_TYPE_MEMREF_OUTPUT);

	struct aes_cipher *sess;
	sess = (struct aes_cipher *)session;
	printf("***************Button is Pressed inside entry fun****************\n");
	//unsigned char data[16] = {0};
	//data[0]= 0x01;
	output(sess, param_types, params);
	return TEE_SUCCESS;
}

//=========================================================================

// Called when the TA is created =======================================
TEE_Result TA_CreateEntryPoint(void) {
   DMSG("=============== TA_CreateEntryPoint ================");
   return TEE_SUCCESS;
}

// Called when the TA is destroyed
void TA_DestroyEntryPoint(void) {
   DMSG("=============== TA_DestroyEntryPoint ===============");
}

// open session  
TEE_Result TA_OpenSessionEntryPoint(uint32_t __unused param_types,
					TEE_Param __unused params[4],
					void __unused **session)
{
   DMSG("=========== TA_OpenSessionEntryPoint ===============");

	struct aes_cipher *sess;
	sess = TEE_Malloc(sizeof(*sess), 0);
	if (!sess)
		return TEE_ERROR_OUT_OF_MEMORY;

	sess->key_handle = TEE_HANDLE_NULL;
	sess->op_handle = TEE_HANDLE_NULL;

	*session = (void *)sess;
	DMSG("Session %p: newly allocated", *session);

	return TEE_SUCCESS;
}

// close session
void TA_CloseSessionEntryPoint(void *session)
{
   DMSG("========== TA_CloseSessionEntryPoint ===============");

	struct aes_cipher *sess;

	/* Get ciphering context from session ID */
	DMSG("Session %p: release session", session);
	sess = (struct aes_cipher *)session;

	/* Release the session resources */
	if (sess->key_handle != TEE_HANDLE_NULL)
		TEE_FreeTransientObject(sess->key_handle);
	if (sess->op_handle != TEE_HANDLE_NULL)
		TEE_FreeOperation(sess->op_handle);
	TEE_Free(sess);
}

// invoke command
TEE_Result TA_InvokeCommandEntryPoint(void *session, uint32_t cmd, uint32_t param_types,
					TEE_Param params[4])
{
	printf("#################Invoking##########################\n");
	switch (cmd) {
	case SET_KEY:
		return set_key(session, param_types, params);
	case ATTEST:
		return attest(session, param_types, params);
	case HANDLE_INPUT:
		return TEE_SUCCESS;
	case ENTRY:
		return entry(session, param_types, params);
	default:
		EMSG("Command ID 0x%x is not supported", cmd);
		return TEE_ERROR_NOT_SUPPORTED;
	}
}
