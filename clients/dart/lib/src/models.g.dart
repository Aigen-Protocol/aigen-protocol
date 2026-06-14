// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'models.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

Reward _$RewardFromJson(Map<String, dynamic> json) => Reward(
      amount: json['amount'] as num,
      currency: $enumDecode(_$RewardCurrencyEnumMap, json['currency']),
    );

Map<String, dynamic> _$RewardToJson(Reward instance) => <String, dynamic>{
      'amount': instance.amount,
      'currency': _$RewardCurrencyEnumMap[instance.currency]!,
    };

const _$RewardCurrencyEnumMap = {
  RewardCurrency.aigen: 'AIGEN',
  RewardCurrency.usdc: 'USDC',
};
