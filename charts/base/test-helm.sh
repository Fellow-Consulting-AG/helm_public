#!/bin/bash

# Helm Chart Testing Script
# Tests various configurations to ensure templates work correctly

set -e  # Exit on first error

echo "================================"
echo "Helm Chart Comprehensive Testing"
echo "================================"

CHART_DIR="/Users/daniel/DocBits/helm_public/charts/base"
TEST_VALUES_DIR="$CHART_DIR/test-values"
FAILED_TESTS=0
PASSED_TESTS=0

# Function to run a test
run_test() {
    local test_name=$1
    local values_file=$2
    local should_fail=${3:-false}

    echo ""
    echo "Test: $test_name"
    echo "Values: $values_file"
    echo "----------------------------------------"

    if [ "$should_fail" = "true" ]; then
        if helm template test "$CHART_DIR" -f "$values_file" > /dev/null 2>&1; then
            echo "❌ FAILED: Expected template to fail but it succeeded"
            ((FAILED_TESTS++))
            return 1
        else
            echo "✅ PASSED: Template failed as expected"
            ((PASSED_TESTS++))
            return 0
        fi
    else
        if output=$(helm template test "$CHART_DIR" -f "$values_file" 2>&1); then
            echo "✅ PASSED: Template rendered successfully"

            # Additional checks for specific tests
            case $test_name in
                "No ingress defined")
                    if echo "$output" | grep -q "kind: Ingress"; then
                        echo "❌ FAILED: Ingress should not be created"
                        ((FAILED_TESTS++))
                        return 1
                    fi
                    ;;
                "Ingress disabled")
                    if echo "$output" | grep -q "kind: Ingress"; then
                        echo "❌ FAILED: Ingress should not be created when disabled"
                        ((FAILED_TESTS++))
                        return 1
                    fi
                    ;;
                "Multiple ingresses")
                    ingress_count=$(echo "$output" | grep -c "kind: Ingress" || true)
                    if [ "$ingress_count" -ne 2 ]; then
                        echo "❌ FAILED: Expected 2 ingresses, got $ingress_count"
                        ((FAILED_TESTS++))
                        return 1
                    fi
                    ;;
                "Service without enabled")
                    if ! echo "$output" | grep -q "kind: Service"; then
                        echo "❌ FAILED: Service should be created when enabled key is missing"
                        ((FAILED_TESTS++))
                        return 1
                    fi
                    ;;
            esac

            ((PASSED_TESTS++))
            return 0
        else
            echo "❌ FAILED: Template rendering failed"
            echo "Error: $output"
            ((FAILED_TESTS++))
            return 1
        fi
    fi
}

# Run helm lint first
echo "Running helm lint..."
if helm lint "$CHART_DIR" > /dev/null 2>&1; then
    echo "✅ Helm lint passed"
else
    echo "❌ Helm lint failed"
    exit 1
fi

# Test 1: No ingress defined
run_test "No ingress defined" "$TEST_VALUES_DIR/1-no-ingress.yaml"

# Test 2: Ingress explicitly disabled
run_test "Ingress disabled" "$TEST_VALUES_DIR/2-ingress-disabled.yaml"

# Test 3: Single ingress as map
run_test "Single ingress" "$TEST_VALUES_DIR/3-ingress-single.yaml"

# Test 4: Multiple ingresses as list
run_test "Multiple ingresses" "$TEST_VALUES_DIR/4-ingress-list.yaml"

# Test 5: Old ingress format (serviceName/servicePort)
run_test "Old ingress format" "$TEST_VALUES_DIR/5-old-ingress-format.yaml"

# Test 6: Service as list
run_test "Service as list" "$TEST_VALUES_DIR/6-service-list.yaml"

# Test 7: No service defined
run_test "No service defined" "$TEST_VALUES_DIR/7-no-service.yaml"

# Test 8: Service without enabled key
run_test "Service without enabled" "$TEST_VALUES_DIR/8-service-no-enabled.yaml"

# Test with --set flags
echo ""
echo "Test: Using --set flags"
echo "----------------------------------------"
if helm template test "$CHART_DIR" --set ingress.enabled=false --set service.enabled=true > /dev/null 2>&1; then
    echo "✅ PASSED: --set flags work correctly"
    ((PASSED_TESTS++))
else
    echo "❌ FAILED: --set flags failed"
    ((FAILED_TESTS++))
fi

# Test with empty values
echo ""
echo "Test: Empty values file"
echo "----------------------------------------"
if helm template test "$CHART_DIR" > /dev/null 2>&1; then
    echo "✅ PASSED: Works with default values"
    ((PASSED_TESTS++))
else
    echo "❌ FAILED: Failed with default values"
    ((FAILED_TESTS++))
fi

# Test 9: Multi-release deployment (unique ConfigMap names)
echo ""
echo "Test: Multi-release deployment (unique ConfigMaps)"
echo "----------------------------------------"
output1=$(helm template api "$CHART_DIR" -f "$TEST_VALUES_DIR/9-multi-release.yaml" 2>&1)
output2=$(helm template api-celery "$CHART_DIR" -f "$TEST_VALUES_DIR/9-multi-release.yaml" 2>&1)

if echo "$output1" | grep -q "name: api-base-debug"; then
    if echo "$output2" | grep -q "name: api-celery-base-debug"; then
        echo "✅ PASSED: Each release has unique ConfigMap name"
        ((PASSED_TESTS++))
    else
        echo "❌ FAILED: Second release ConfigMap not unique"
        ((FAILED_TESTS++))
    fi
else
    echo "❌ FAILED: First release ConfigMap not using release name"
    ((FAILED_TESTS++))
fi

# Summary
echo ""
echo "================================"
echo "Test Summary"
echo "================================"
echo "✅ Passed: $PASSED_TESTS"
echo "❌ Failed: $FAILED_TESTS"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo "🎉 All tests passed successfully!"
    exit 0
else
    echo "⚠️  Some tests failed. Please review the output above."
    exit 1
fi