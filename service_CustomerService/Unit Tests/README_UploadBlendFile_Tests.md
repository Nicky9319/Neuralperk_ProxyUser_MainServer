# Customer Service - Upload Blend File API Tests

This directory contains comprehensive test collections for the Customer Service upload blend file API endpoint.

## Files

1. **`CustomerService_UploadBlendFile_Tests.postman_collection.json`** - Main test collection with 8 test scenarios
2. **`CustomerService_Test_Environment.postman_environment.json`** - Environment variables for testing
3. **`README_UploadBlendFile_Tests.md`** - This documentation file

## Test Scenarios

### 1. Success Case
- **Purpose**: Tests successful blend file upload with valid authentication and file data
- **Expected Result**: 200 OK with object ID, file path, and success message
- **What it tests**: Complete flow from MongoDB object creation to blob storage to database update

### 2. Missing Authentication
- **Purpose**: Tests upload attempt without Authorization header
- **Expected Result**: 401 Unauthorized
- **What it tests**: Authentication middleware enforcement

### 3. Invalid Access Token
- **Purpose**: Tests upload attempt with invalid Bearer token
- **Expected Result**: 401 Unauthorized
- **What it tests**: Token validation in authentication middleware

### 4. Missing File Name
- **Purpose**: Tests upload attempt without blend file name
- **Expected Result**: 422 Unprocessable Entity
- **What it tests**: Required field validation

### 5. Missing File
- **Purpose**: Tests upload attempt without the actual blend file
- **Expected Result**: 422 Unprocessable Entity
- **What it tests**: Required field validation

### 6. Missing Customer ID
- **Purpose**: Tests upload attempt without customer ID
- **Expected Result**: 422 Unprocessable Entity
- **What it tests**: Required field validation

### 7. Different File Types
- **Purpose**: Tests upload with various file types
- **Expected Result**: Varies based on file type
- **What it tests**: File handling and validation

### 8. Large File
- **Purpose**: Tests upload with larger files
- **Expected Result**: 200 OK (if successful)
- **What it tests**: Performance and storage handling

## Setup Instructions

### 1. Import Test Collection
1. Open Postman
2. Click "Import" button
3. Select `CustomerService_UploadBlendFile_Tests.postman_collection.json`
4. The collection will be imported with all test scenarios

### 2. Import Environment
1. In Postman, click "Import" button
2. Select `CustomerService_Test_Environment.postman_environment.json`
3. Select the imported environment from the environment dropdown (top-right corner)

### 3. Update Environment Variables
**Important**: Update these values to match your actual system:

- **`test_customer_id`**: Set to a valid customer ID that exists in your MongoDB
- **`valid_access_token`**: Set to a valid Bearer token that your auth service recognizes
- **`base_url`**: Update if your Customer Service runs on a different port/host

### 4. Prepare Test Files
For the file upload tests, you'll need:
- A `.blend` file for testing (can be any Blender file)
- Different file types for testing validation
- Files of various sizes for performance testing

## Running the Tests

### Individual Test Execution
1. Select the test collection in Postman
2. Choose a specific test scenario
3. Click "Send" to execute
4. Review the response and test results

### Collection Runner
1. Click the "Run" button on the collection
2. Select which tests to run
3. Choose the test environment
4. Click "Run Customer Service - Upload Blend File Tests"

### Newman CLI (Automated Testing)
```bash
# Install Newman if not already installed
npm install -g newman

# Run the collection
newman run "CustomerService_UploadBlendFile_Tests.postman_collection.json" \
  -e "CustomerService_Test_Environment.postman_environment.json" \
  --reporters cli,json \
  --reporter-json-export results.json
```

## Test Validation

The tests automatically validate:

### Response Structure
- Status codes (200, 201, 401, 422, 500)
- Response time (should be < 10 seconds)
- JSON response format

### Success Case Validation
- All required fields are present
- Object ID is valid UUID format
- Blend file path follows naming convention
- Status is "uploaded"

### Error Case Validation
- Authentication errors return 401
- Validation errors return 422
- Error responses have proper detail messages

### Data Persistence
- MongoDB object creation
- Blob storage file upload
- Database path updates

## Troubleshooting

### Common Issues

1. **401 Unauthorized Errors**
   - Check if `valid_access_token` is set correctly
   - Verify your auth service is running
   - Ensure the token is valid and not expired

2. **422 Validation Errors**
   - Verify all required fields are provided
   - Check file upload format (multipart/form-data)
   - Ensure file size is within limits

3. **500 Internal Server Errors**
   - Check if MongoDB service is running (port 12000)
   - Check if Blob service is running (port 13000)
   - Review service logs for detailed error information

4. **Connection Refused Errors**
   - Verify all services are running on expected ports
   - Check firewall and network settings
   - Ensure services are accessible from your testing environment

### Debug Mode
Enable debug logging in Postman:
1. Go to Postman Settings
2. Enable "Show Postman Console"
3. Check console for detailed request/response information

## Service Dependencies

The upload blend file API depends on these services:

1. **Customer Service** (Port 11000) - Main API endpoint
2. **Auth Service** (Port 10000) - Token validation
3. **MongoDB Service** (Port 12000) - Database operations
4. **Blob Service** (Port 13000) - File storage

Ensure all services are running before executing tests.

## Expected API Flow

```
1. Client Request → Customer Service
2. Customer Service → Auth Service (validate token)
3. Customer Service → MongoDB Service (create object)
4. Customer Service → Blob Service (store file)
5. Customer Service → MongoDB Service (update path)
6. Customer Service → Client (success response)
```

## Performance Considerations

- **Response Time**: Tests expect responses under 10 seconds
- **File Size**: Test with various file sizes to verify performance
- **Concurrent Requests**: Consider testing multiple simultaneous uploads
- **Memory Usage**: Monitor service memory usage during large file uploads

## Security Testing

The tests cover:
- Authentication bypass attempts
- Invalid token handling
- Missing required fields
- File type validation

## Maintenance

- Update test data regularly
- Monitor test results for regressions
- Update environment variables when service configurations change
- Add new test scenarios as the API evolves
