import argparse


def create_parser():
    parser = argparse.ArgumentParser(
        description='Imports Unreal Engine releases into plastic vendor branches'
    )
    return parser


def main():
    parser = create_parser()
    parser.parse_args()

    print('Hello world')
    return 0
